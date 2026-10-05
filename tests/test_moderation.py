from lyceum.application.cards import NEEDS_TEXT_MESSAGE, SERIES_LATER_NOTICE
from lyceum.application.moderation import THEME_NAME_REJECTED, STARTER_THEMES, ensure_starter_themes
from lyceum.domain.protocols import FetchedPage
from lyceum.domain.status import ArticleStatus
from lyceum.domain.text import (
    FORUM_TEXT_LIMIT,
    MIN_USABLE_TEXT_CHARS,
    is_usable_article_text,
    split_summary,
)
from lyceum.handlers.moderation import render_card
from tests.conftest import CHANNEL_CHAT_ID, LONG_TEXT
from tests.fakes import FIXED_SUMMARY

URL = "https://example.com/django-n-plus-one"


def test_threshold_is_four_hundred_characters() -> None:
    assert MIN_USABLE_TEXT_CHARS == 400
    assert is_usable_article_text("а" * 399) is False
    assert is_usable_article_text("а" * 400) is True


def test_url_reaches_moderation_card(harness) -> None:
    assert len(LONG_TEXT) >= MIN_USABLE_TEXT_CHARS
    harness.fetcher.pages[URL] = FetchedPage(title="N+1 в Django", text=LONG_TEXT)
    outcome = harness.service.submit_url(URL)
    stored = harness.articles.get(outcome.article.require_id())

    assert harness.fetcher.calls == [URL]
    assert harness.summarizer.calls == [stored.raw_text]
    assert stored.status is ArticleStatus.AWAITING_REVIEW
    assert stored.summary == FIXED_SUMMARY
    assert outcome.card.title == "N+1 в Django"
    assert outcome.card.source_label == URL
    assert outcome.card.summary == FIXED_SUMMARY
    assert outcome.card.theme_title is None
    assert outcome.card.publish_available is False
    assert outcome.published is False
    assert harness.publisher.messages == []


def test_ready_post_skips_summarizer(harness) -> None:
    text = "Готовый пост: индекс закрывает этот запрос."
    outcome = harness.service.submit_ready_post(text)
    stored = harness.articles.get(outcome.article.require_id())

    assert harness.summarizer.calls == []
    assert harness.fetcher.calls == []
    assert stored.status is ArticleStatus.AWAITING_REVIEW
    assert stored.summary == text
    assert outcome.card.summary == text
    assert outcome.card.source_label == "Готовый пост"
    assert harness.publisher.messages == []


def test_short_text_is_not_published(harness) -> None:
    outcome = harness.service.submit_text("Войдите, чтобы читать.")
    article_id = outcome.article.require_id()

    assert outcome.article.status is not ArticleStatus.AWAITING_REVIEW
    assert outcome.card.needs_text is True
    assert outcome.card.hint == NEEDS_TEXT_MESSAGE
    assert NEEDS_TEXT_MESSAGE in render_card(outcome.card)
    assert harness.summarizer.calls == []
    assert harness.fetcher.calls == []

    approved = harness.service.approve(article_id)
    assert approved.published is False
    assert harness.publisher.messages == []
    assert harness.articles.get(article_id).status is not ArticleStatus.PUBLISHED


def test_text_below_threshold_stays_off_review(harness) -> None:
    outcome = harness.service.submit_text("б" * (MIN_USABLE_TEXT_CHARS - 1))
    assert outcome.article.status is ArticleStatus.EXTRACTED
    assert outcome.card.needs_text is True
    assert harness.summarizer.calls == []


def test_russian_title_replaces_the_opening_line(harness) -> None:
    harness.summarizer.summary = "Заголовок: Четыре инструмента ORM\n\nQ, F, annotate и aggregate."
    text = "Most Django developers use maybe 20% of the ORM. " * 20
    outcome = harness.service.submit_text(text)
    stored = harness.articles.get(outcome.article.require_id())

    assert outcome.card.title == "Четыре инструмента ORM"
    assert stored.title == "Четыре инструмента ORM"
    assert outcome.card.summary == "Q, F, annotate и aggregate."
    assert "Most Django" not in outcome.card.summary


def test_summary_without_title_line_stays_intact() -> None:
    title, body = split_summary("Только выжимка без отдельного заголовка.")
    assert title is None
    assert body == "Только выжимка без отдельного заголовка."


def test_text_at_threshold_reaches_review(harness) -> None:
    text = "в" * MIN_USABLE_TEXT_CHARS
    outcome = harness.service.submit_text(text)
    assert outcome.article.status is ArticleStatus.AWAITING_REVIEW
    assert harness.summarizer.calls == [text]
    assert outcome.card.summary == FIXED_SUMMARY


def test_approve_without_theme_does_not_publish(harness) -> None:
    article_id = _reviewed_url(harness)
    outcome = harness.service.approve(article_id)

    assert outcome.published is False
    assert outcome.card.publish_available is False
    assert harness.publisher.messages == []
    assert harness.publications.get_by_article(article_id) is None
    assert harness.articles.get(article_id).status is ArticleStatus.AWAITING_REVIEW


def test_approve_with_theme_publishes_once(harness) -> None:
    article_id = _reviewed_url(harness)
    theme = harness.add_theme()
    chosen = harness.service.choose_theme(article_id, theme.require_id())
    assert chosen.card.publish_available is True
    assert chosen.card.theme_title == "Django"
    rendered = render_card(chosen.card)
    assert "Тема: Django" in rendered
    assert "Ветка" not in rendered

    first = harness.service.approve(article_id)
    second = harness.service.approve(article_id)

    assert first.published is True
    assert second.published is False
    assert len(harness.publisher.messages) == 1
    post = harness.publisher.messages[0]
    assert post.telegram_chat_id == str(CHANNEL_CHAT_ID)
    assert FIXED_SUMMARY in post.text
    assert len(post.text) <= FORUM_TEXT_LIMIT
    assert "Реклама" not in post.text
    stored = harness.publications.get_by_article(article_id)
    assert stored is not None
    assert stored.telegram_chat_id == CHANNEL_CHAT_ID
    assert stored.telegram_message_id == 501
    assert stored.url.endswith("/501")
    assert harness.articles.get(article_id).status is ArticleStatus.PUBLISHED


def test_changing_theme_does_not_rewrite_publication(harness) -> None:
    article_id = _reviewed_url(harness)
    theme = harness.add_theme()
    harness.service.choose_theme(article_id, theme.require_id())
    harness.service.approve(article_id)

    theme.title = "FastAPI"
    theme.slug = "fastapi"
    harness.themes.save(theme)

    stored = harness.publications.get_by_article(article_id)
    assert stored is not None
    assert stored.telegram_chat_id == CHANNEL_CHAT_ID
    assert stored.telegram_message_id == 501
    again = harness.service.approve(article_id)
    assert again.published is False
    assert len(harness.publisher.messages) == 1


def test_channel_text_is_capped_at_4096(harness) -> None:
    article_id = _reviewed_url(harness)
    harness.service.edit_summary(article_id, "я" * 5000)
    theme = harness.add_theme()
    harness.service.choose_theme(article_id, theme.require_id())
    harness.service.approve(article_id)
    assert len(harness.publisher.messages[0].text) == FORUM_TEXT_LIMIT


def test_reject_does_not_publish(harness) -> None:
    article_id = _reviewed_url(harness)
    theme = harness.add_theme()
    harness.service.choose_theme(article_id, theme.require_id())
    rejected = harness.service.reject(article_id)
    later = harness.service.approve(article_id)

    assert rejected.article.status is ArticleStatus.REJECTED
    assert later.published is False
    assert harness.publisher.messages == []
    assert harness.publications.get_by_article(article_id) is None
    assert harness.articles.get(article_id).status is ArticleStatus.REJECTED


def test_edit_summary_updates_card(harness) -> None:
    article_id = _reviewed_url(harness)
    edited = "Новая выжимка: смотреть план запроса, а не только время ответа."
    outcome = harness.service.edit_summary(article_id, edited)
    stored = harness.articles.get(article_id)

    assert stored.summary == edited
    assert stored.status is ArticleStatus.AWAITING_REVIEW
    assert outcome.card.summary == edited
    assert outcome.card.article_id == article_id
    assert harness.publisher.messages == []


def test_reject_during_summary_is_not_overwritten(harness) -> None:
    article_id = _reviewed_url(harness)

    def reject_while_summarizing() -> None:
        article = harness.articles.get(article_id)
        article.reject()
        harness.articles.save(article)

    harness.summarizer.summary = "Поздняя выжимка, которую нельзя записать."
    harness.summarizer.on_summarize = reject_while_summarizing
    outcome = harness.service.regenerate(article_id)
    stored = harness.articles.get(article_id)

    assert stored.status is ArticleStatus.REJECTED
    assert stored.summary == FIXED_SUMMARY
    assert outcome.article.status is ArticleStatus.REJECTED
    assert outcome.card.actions == ()
    assert outcome.card.summary == FIXED_SUMMARY
    assert harness.publisher.messages == []


def test_regenerate_calls_summarizer_again(harness) -> None:
    article_id = _reviewed_url(harness)
    harness.service.edit_summary(article_id, "Черновик, который надо переделать.")
    outcome = harness.service.regenerate(article_id)

    assert len(harness.summarizer.calls) == 2
    assert outcome.card.summary == FIXED_SUMMARY
    assert outcome.article.status is ArticleStatus.AWAITING_REVIEW
    assert harness.publisher.messages == []


def test_series_button_does_not_publish(harness) -> None:
    article_id = _reviewed_url(harness)
    outcome = harness.service.enqueue_series(article_id)

    assert outcome.notice == SERIES_LATER_NOTICE
    assert outcome.published is False
    assert harness.publisher.messages == []
    assert harness.articles.get(article_id).status is ArticleStatus.AWAITING_REVIEW


def test_ready_post_regenerate_does_not_call_summarizer(harness) -> None:
    outcome = harness.service.submit_ready_post("Короткий готовый пост остаётся как есть.")
    again = harness.service.regenerate(outcome.article.require_id())
    assert harness.summarizer.calls == []
    assert again.article.summary == "Короткий готовый пост остаётся как есть."
    assert harness.publisher.messages == []


def test_named_theme_is_selected_for_the_article(harness) -> None:
    article_id = _reviewed_url(harness)
    created = harness.service.attach_named_theme(article_id, "  Redis  ")
    again = harness.service.attach_named_theme(article_id, "Redis")
    titles = [theme.title for theme in harness.themes.list_all()]

    assert created.notice == "Тема «Redis» добавлена."
    assert created.card.theme_title == "Redis"
    assert created.card.publish_available is True
    assert again.notice == "Тема уже есть, выбираю её."
    assert again.card.publish_available is True
    assert titles.count("Redis") == 1


def test_theme_name_is_rejected_before_insert(harness) -> None:
    article_id = _reviewed_url(harness)
    blank = harness.service.attach_named_theme(article_id, "   ")
    too_long = harness.service.attach_named_theme(article_id, "я" * 81)
    fits = harness.service.attach_named_theme(article_id, "я" * 80)

    assert blank.notice == THEME_NAME_REJECTED
    assert too_long.notice == THEME_NAME_REJECTED
    assert blank.card.theme_title is None
    assert fits.card.theme_title == "я" * 80
    assert [theme.slug for theme in harness.themes.list_all()] == ["я" * 80]


def test_register_theme_does_not_attach_to_article(harness) -> None:
    article_id = _reviewed_url(harness)
    created = harness.service.register_theme("Redis")
    repeat = harness.service.register_theme("Redis")

    assert created == "Тема «Redis» добавлена."
    assert repeat == "Тема «Redis» уже есть."
    assert harness.articles.get(article_id).theme_id is None


def test_starter_themes_are_not_duplicated(harness) -> None:
    harness.add_theme(title="Django", slug="Django")
    ensure_starter_themes(harness.themes)
    ensure_starter_themes(harness.themes)
    slugs = [theme.slug for theme in harness.themes.list_all()]

    assert slugs.count("Django") == 1
    assert set(STARTER_THEMES) <= set(slugs)


def _reviewed_url(harness) -> int:
    harness.fetcher.pages[URL] = FetchedPage(title="N+1 в Django", text=LONG_TEXT)
    outcome = harness.service.submit_url(URL)
    return outcome.article.require_id()
