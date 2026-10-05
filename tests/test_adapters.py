import json
from types import SimpleNamespace

import httpx
import pytest

from lyceum.domain.protocols import OutboundPost
from lyceum.infrastructure.fetching import TrafilaturaFetcher
from lyceum.infrastructure.publishing import TelegramChannelPublisher
from lyceum.infrastructure.summarizing import CursorSummarizer, build_summarizer


def test_fetcher_reads_html_without_network() -> None:
    paragraph = "Разбор N+1 в Django ORM и лишних запросов к базе. " * 30
    html = (
        "<!DOCTYPE html><html><head><title>N+1 в Django</title></head>"
        f"<body><article><h1>N+1 в Django</h1><p>{paragraph}</p></article></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "example.com"
        return httpx.Response(200, text=html)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    page = TrafilaturaFetcher(client).fetch("https://example.com/django-n-plus-one")
    assert "N+1" in (page.title or "")
    assert "лишних запросов" in page.text


def test_fake_summarizer_does_not_call_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("Тест вызвал Cursor")

    monkeypatch.setattr("lyceum.infrastructure.summarizing.Agent.prompt", fail)
    summarizer = build_summarizer("fake", "not-a-real-key")
    with pytest.raises(RuntimeError, match="SUMMARIZER=cursor"):
        summarizer.summarize("текст статьи")


def test_cursor_summarizer_without_key_does_not_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("Тест вызвал Cursor")

    monkeypatch.setattr("lyceum.infrastructure.summarizing.Agent.prompt", fail)
    with pytest.raises(RuntimeError, match="CURSOR_API_KEY"):
        CursorSummarizer("").summarize("текст статьи")


def test_cursor_summarizer_asks_cloud_agent_without_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_prompt(message: str, options: object = None, *, client: object = None) -> SimpleNamespace:
        del client
        seen["message"] = message
        seen["options"] = options
        return SimpleNamespace(status="finished", result="  Русская выжимка.  ")

    monkeypatch.setattr("lyceum.infrastructure.summarizing.Agent.prompt", fake_prompt)
    summary = CursorSummarizer("not-a-real-key").summarize("Текст статьи.", title="N+1")

    assert summary == "Русская выжимка."
    message = seen["message"]
    assert isinstance(message, str)
    assert "N+1" in message
    assert "Текст статьи." in message
    assert "Заголовок: короткий русский заголовок" in message
    assert "Оригинальный заголовок, его нужно перевести: N+1" in message
    assert "короткую выжимку" not in message
    options = seen["options"]
    assert options is not None
    assert options.api_key == "not-a-real-key"
    assert options.model == "composer-2.5"
    assert options.local is None
    assert options.cloud is not None
    assert list(options.cloud.repos) == []


def test_cursor_summarizer_rejects_failed_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_prompt(message: str, options: object = None, *, client: object = None) -> SimpleNamespace:
        del message, options, client
        return SimpleNamespace(status="error", result="")

    monkeypatch.setattr("lyceum.infrastructure.summarizing.Agent.prompt", fake_prompt)
    with pytest.raises(RuntimeError, match="не получено"):
        CursorSummarizer("not-a-real-key").summarize("Текст статьи.")


def test_private_channel_link_drops_minus_100_prefix() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["chat_id"] == "-1001234567890"
        assert body["text"] == "Выжимка"
        assert "message_thread_id" not in body
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 15,
                    "chat": {"id": -1001234567890, "type": "channel"},
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    publisher = TelegramChannelPublisher("not-a-real-token", "-1001234567890", client=client)
    receipt = publisher.publish(
        OutboundPost(article_id=1, telegram_chat_id="-1001234567890", text="Выжимка")
    )
    assert receipt.telegram_chat_id == -1001234567890
    assert receipt.telegram_message_id == 15
    assert receipt.url == "https://t.me/c/1234567890/15"
    assert "-100" not in receipt.url


def test_public_channel_link_uses_username() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 8,
                    "chat": {"id": -1001234567890, "username": "example", "type": "channel"},
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    publisher = TelegramChannelPublisher("not-a-real-token", "@example", client=client)
    receipt = publisher.publish(
        OutboundPost(article_id=1, telegram_chat_id="@example", text="Выжимка")
    )
    assert receipt.url == "https://t.me/example/8"


def test_publisher_without_token_does_not_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("Тест вызвал Telegram")

    monkeypatch.setattr(httpx.Client, "post", fail)
    publisher = TelegramChannelPublisher("", "-1001234567890")
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        publisher.publish(OutboundPost(article_id=1, telegram_chat_id="-100", text="Выжимка"))
