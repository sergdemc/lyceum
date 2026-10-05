from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from lyceum.domain.article import Article
from lyceum.domain.status import ArticleSource, ArticleStatus
from lyceum.domain.text import FORUM_TEXT_LIMIT
from lyceum.domain.theme import Theme

NEEDS_TEXT_MESSAGE = 'Текст не извлечён. Страница пустая или это стена логина — вставьте текст статьи.'
CHOOSE_THEME_MESSAGE = '«Опубликовать» доступно после выбора темы.'
SERIES_LATER_NOTICE = 'Серия будет в следующем срезе.'


class ModerationAction(StrEnum):
    PUBLISH = 'publish'
    SERIES = 'series'
    REGENERATE = 'regenerate'
    EDIT = 'edit'
    REJECT = 'reject'


NEW_THEME_ACTION = 'new_theme'

REVIEW_ACTIONS: tuple[ModerationAction, ...] = (
    ModerationAction.PUBLISH,
    ModerationAction.SERIES,
    ModerationAction.REGENERATE,
    ModerationAction.EDIT,
    ModerationAction.REJECT,
)


@dataclass(frozen=True)
class ThemeOption:
    id: int
    title: str
    selected: bool


@dataclass(frozen=True)
class ModerationCard:
    article_id: int
    title: str
    source_label: str
    summary: str
    theme_title: str | None
    publish_available: bool
    needs_text: bool
    hint: str | None
    actions: tuple[ModerationAction, ...]
    themes: tuple[ThemeOption, ...]


@dataclass(frozen=True)
class ModerationOutcome:
    article: Article
    card: ModerationCard
    published: bool = False
    notice: str | None = None


def source_label(article: Article) -> str:
    if article.source is ArticleSource.URL:
        return article.origin_url or 'Ссылка'
    if article.source is ArticleSource.READY_POST:
        return 'Готовый пост'
    return 'Свой текст'


def publication_text(article: Article) -> str:
    title = article.title or 'Без заголовка'
    body = f'{title}\n\n{article.summary}'
    if len(body) <= FORUM_TEXT_LIMIT:
        return body
    return body[:FORUM_TEXT_LIMIT]


def build_card(article: Article, themes: Sequence[Theme]) -> ModerationCard:
    article_id = article.require_id()
    in_review = article.status is ArticleStatus.AWAITING_REVIEW
    needs_text = article.needs_manual_text()
    publish_available = in_review and article.theme_id is not None
    selected_theme: str | None = None
    options: list[ThemeOption] = []
    for theme in themes:
        theme_id = theme.id
        if theme_id is None:
            continue
        selected = theme_id == article.theme_id
        if selected:
            selected_theme = theme.title
        if in_review:
            options.append(ThemeOption(id=theme_id, title=theme.title, selected=selected))
    if needs_text:
        hint: str | None = NEEDS_TEXT_MESSAGE
    elif in_review and not publish_available:
        hint = CHOOSE_THEME_MESSAGE
    else:
        hint = None
    return ModerationCard(
        article_id=article_id,
        title=article.title or 'Без заголовка',
        source_label=source_label(article),
        summary=article.summary,
        theme_title=selected_theme,
        publish_available=publish_available,
        needs_text=needs_text,
        hint=hint,
        actions=REVIEW_ACTIONS if in_review else (),
        themes=tuple(options),
    )
