from lyceum.application.cards import REVIEW_ACTIONS, ModerationCard, ThemeOption
from lyceum.domain.status import ArticleStatus
from lyceum.handlers.moderation import _Drafts, append_part, moderation_keyboard


def _texts(card: ModerationCard) -> list[str]:
    markup = moderation_keyboard(card)
    return [button.text for row in markup.inline_keyboard for button in row]


def test_publish_is_hidden_until_theme_is_chosen() -> None:
    card = ModerationCard(
        article_id=1,
        title="N+1 в Django",
        source_label="https://example.com/django-n-plus-one",
        summary="Выжимка",
        theme_title=None,
        publish_available=False,
        needs_text=False,
        hint="«Опубликовать» доступно после выбора темы.",
        actions=REVIEW_ACTIONS,
        themes=(ThemeOption(id=7, title="Django", selected=False),),
    )
    texts = _texts(card)
    assert "Опубликовать" not in texts
    assert texts == ["В серию", "Переделать", "Править", "Отклонить", "Django", "Новая тема"]


def test_publish_appears_when_theme_is_selected() -> None:
    card = ModerationCard(
        article_id=1,
        title="N+1 в Django",
        source_label="https://example.com/django-n-plus-one",
        summary="Выжимка",
        theme_title="Django",
        publish_available=True,
        needs_text=False,
        hint=None,
        actions=REVIEW_ACTIONS,
        themes=(ThemeOption(id=7, title="Django", selected=True),),
    )
    assert _texts(card) == [
        "Опубликовать",
        "В серию",
        "Переделать",
        "Править",
        "Отклонить",
        "✓ Django",
        "Новая тема",
    ]


def test_second_part_replaces_the_first_submit() -> None:
    drafts = _Drafts()
    first = drafts.remember(1, "text", buffer="начало")
    second = drafts.remember(1, "text", buffer=append_part("начало", "конец"))
    assert drafts.take(1, first) is None
    taken = drafts.take(1, second)
    assert taken is not None
    assert taken.buffer == "начало\nконец"


def test_forget_drops_a_waiting_draft() -> None:
    drafts = _Drafts()
    token = drafts.remember(1, "text", buffer="начало")
    drafts.forget(1)
    assert drafts.take(1, token) is None


def test_future_status_names_stay_reserved() -> None:
    assert ArticleStatus.SCHEDULED == "scheduled"
    assert ArticleStatus.PUBLISHED == "published"
    assert ArticleStatus.APPROVED == "approved"
