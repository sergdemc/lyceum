from datetime import datetime, timezone

from lyceum.application.cards import (
    SERIES_LATER_NOTICE,
    ModerationOutcome,
    build_card,
    publication_text,
)
from lyceum.domain.article import Article
from lyceum.domain.protocols import (
    ArticleFetcher,
    ArticleRepository,
    OutboundPost,
    PublicationRepository,
    Publisher,
    Summarizer,
    ThemeRepository,
)
from lyceum.domain.publication import Publication
from lyceum.domain.status import ArticleSource, ArticleStatus
from lyceum.domain.text import is_usable_article_text, split_summary, title_from_text
from lyceum.domain.theme import Theme

THEME_NAME_LIMIT = 80
THEME_NAME_REJECTED = 'Название не подошло.'
STARTER_THEMES = ('Django', 'FastAPI', 'Postgres', 'модели', 'агенты')


def ensure_starter_themes(themes: ThemeRepository) -> None:
    present = {theme.slug for theme in themes.list_all()}
    for title in STARTER_THEMES:
        if title in present:
            continue
        themes.add(Theme(title=title, slug=title))
        present.add(title)


class ModerationService:
    """Сценарии модерации. Не знают, какая база и какая модель саммари."""

    def __init__(
        self,
        articles: ArticleRepository,
        themes: ThemeRepository,
        publications: PublicationRepository,
        fetcher: ArticleFetcher,
        summarizer: Summarizer,
        publisher: Publisher,
        channel_chat_id: str,
    ) -> None:
        self._articles = articles
        self._themes = themes
        self._publications = publications
        self._fetcher = fetcher
        self._summarizer = summarizer
        self._publisher = publisher
        self._channel_chat_id = channel_chat_id

    def submit_url(self, url: str) -> ModerationOutcome:
        cleaned_url = url.strip()
        article = Article(source=ArticleSource.URL, origin_url=cleaned_url or None)
        self._articles.add(article)
        if not cleaned_url:
            return self._outcome(article)
        page = self._fetcher.fetch(cleaned_url)
        title = page.title.strip() if page.title and page.title.strip() else title_from_text(page.text)
        article.replace_body(title=title, raw_text=page.text)
        if not is_usable_article_text(article.raw_text):
            self._articles.save(article)
            return self._outcome(article)
        raw_summary = self._read_summary(article, article.raw_text)
        stopped = self._stopped_after_summary(article.require_id())
        if stopped is not None:
            return stopped
        summary = self._apply_title(article, raw_summary)
        article.mark_awaiting_review(summary)
        self._articles.save(article)
        return self._outcome(article)

    def submit_text(self, text: str) -> ModerationOutcome:
        cleaned = text.strip()
        article = Article(
            source=ArticleSource.RAW_TEXT,
            title=title_from_text(cleaned),
            raw_text=cleaned,
        )
        self._articles.add(article)
        if not is_usable_article_text(cleaned):
            if cleaned:
                article.replace_body(title=article.title, raw_text=cleaned)
            self._articles.save(article)
            return self._outcome(article)
        raw_summary = self._read_summary(article, cleaned)
        stopped = self._stopped_after_summary(article.require_id())
        if stopped is not None:
            return stopped
        summary = self._apply_title(article, raw_summary)
        article.replace_body(title=article.title, raw_text=cleaned)
        article.mark_awaiting_review(summary)
        self._articles.save(article)
        return self._outcome(article)

    def submit_ready_post(self, text: str) -> ModerationOutcome:
        cleaned = text.strip()
        article = Article(
            source=ArticleSource.READY_POST,
            title=title_from_text(cleaned) if cleaned else '',
            raw_text=cleaned,
        )
        self._articles.add(article)
        if not cleaned:
            self._articles.save(article)
            return self._outcome(article)
        article.mark_awaiting_review(cleaned)
        self._articles.save(article)
        return self._outcome(article)

    def choose_theme(self, article_id: int, theme_id: int) -> ModerationOutcome:
        article = self._articles.get(article_id)
        theme = self._themes.get(theme_id)
        if article.status is not ArticleStatus.AWAITING_REVIEW:
            return self._outcome(article, notice='Тему можно выбрать, когда статья на модерации.')
        article.assign_theme(theme.require_id())
        self._articles.save(article)
        return self._outcome(article)

    def register_theme(self, name: str) -> str:
        _theme, notice, _created = self._take_theme(name)
        return notice

    def attach_named_theme(self, article_id: int, name: str) -> ModerationOutcome:
        article = self._articles.get(article_id)
        theme, notice, created = self._take_theme(name)
        if theme is None:
            return self._outcome(article, notice=notice)
        if article.status is not ArticleStatus.AWAITING_REVIEW:
            return self._outcome(article, notice='Тему можно выбрать, когда статья на модерации.')
        article.assign_theme(theme.require_id())
        self._articles.save(article)
        if not created:
            notice = 'Тема уже есть, выбираю её.'
        return self._outcome(article, notice=notice)

    def _take_theme(self, name: str) -> tuple[Theme | None, str, bool]:
        cleaned = name.strip()
        if not cleaned or len(cleaned) > THEME_NAME_LIMIT:
            return None, THEME_NAME_REJECTED, False
        found = self._themes.find_by_slug(cleaned)
        if found is not None:
            return found, f'Тема «{cleaned}» уже есть.', False
        theme = self._themes.add(Theme(title=cleaned, slug=cleaned))
        return theme, f'Тема «{cleaned}» добавлена.', True

    def reject(self, article_id: int) -> ModerationOutcome:
        article = self._articles.get(article_id)
        if article.status is not ArticleStatus.AWAITING_REVIEW:
            return self._outcome(article, notice='Отклонить можно только статью на модерации.')
        article.reject()
        self._articles.save(article)
        return self._outcome(article, notice='Отклонено.')

    def edit_summary(self, article_id: int, summary: str) -> ModerationOutcome:
        article = self._articles.get(article_id)
        if article.status is not ArticleStatus.AWAITING_REVIEW:
            return self._outcome(article, notice='Править можно только выжимку на модерации.')
        cleaned = summary.strip()
        if not cleaned:
            return self._outcome(article, notice='Пустая выжимка не сохраняется.')
        article.edit_summary(cleaned)
        self._articles.save(article)
        return self._outcome(article)

    def regenerate(self, article_id: int) -> ModerationOutcome:
        article = self._articles.get(article_id)
        if article.source is ArticleSource.READY_POST:
            return self._outcome(article, notice='Готовый пост не прогоняется через саммари.')
        if article.status is not ArticleStatus.AWAITING_REVIEW:
            return self._outcome(article, notice='Переделать можно только текст на модерации.')
        raw_summary = self._read_summary(article, article.raw_text)
        stopped = self._stopped_after_summary(article_id)
        if stopped is not None:
            return stopped
        summary = self._apply_title(article, raw_summary)
        article.edit_summary(summary)
        self._articles.save(article)
        return self._outcome(article)

    def enqueue_series(self, article_id: int) -> ModerationOutcome:
        article = self._articles.get(article_id)
        return self._outcome(article, notice=SERIES_LATER_NOTICE)

    def approve(self, article_id: int) -> ModerationOutcome:
        article = self._articles.get(article_id)
        if article.status is ArticleStatus.PUBLISHED or self._publications.get_by_article(article_id) is not None:
            return self._outcome(article, notice='Уже опубликовано, повторно не публикую.')
        if article.status is not ArticleStatus.AWAITING_REVIEW:
            return self._outcome(article, notice='Публикация недоступна: статья не на модерации.')
        if article.theme_id is None:
            return self._outcome(
                article,
                notice='Сначала выберите тему. Публикация не выполнена.',
            )
        self._themes.get(article.theme_id)
        receipt = self._publisher.publish(
            OutboundPost(
                article_id=article.require_id(),
                telegram_chat_id=self._channel_chat_id,
                text=publication_text(article),
            )
        )
        self._publications.add(
            Publication(
                article_id=article.require_id(),
                telegram_chat_id=receipt.telegram_chat_id,
                telegram_message_id=receipt.telegram_message_id,
                url=receipt.url,
                published_at=datetime.now(timezone.utc),
            )
        )
        article.mark_published()
        self._articles.save(article)
        return self._outcome(article, published=True, notice='Опубликовано.')

    def _read_summary(self, article: Article, text: str) -> str:
        return self._summarizer.summarize(text, title=article.title or None)

    def _apply_title(self, article: Article, raw: str) -> str:
        title, summary = split_summary(raw)
        if title:
            article.set_title(title)
        return summary

    def _stopped_after_summary(self, article_id: int) -> ModerationOutcome | None:
        current = self._articles.get(article_id)
        if current.status is not ArticleStatus.REJECTED:
            return None
        return self._outcome(current, notice='Выжимка не сохранена: статья отклонена.')

    def _outcome(
        self,
        article: Article,
        *,
        published: bool = False,
        notice: str | None = None,
    ) -> ModerationOutcome:
        return ModerationOutcome(
            article=article,
            card=build_card(article, self._themes.list_all()),
            published=published,
            notice=notice,
        )
