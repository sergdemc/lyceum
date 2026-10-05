import socket
from dataclasses import dataclass
from pathlib import Path

import pytest

from lyceum.application.moderation import ModerationService
from lyceum.domain.theme import Theme
from lyceum.infrastructure.db.repositories import (
    SqlArticleRepository,
    SqlPublicationRepository,
    SqlThemeRepository,
)
from lyceum.infrastructure.db.session import open_session, sqlite_url
from tests.fakes import FakeFetcher, FakePublisher, FakeSummarizer
from tests.support import upgrade_temp_sqlite

LONG_TEXT = "N+1 в Django\n" + ("Абзац про запросы к базе. " * 30)
CHANNEL_CHAT_ID = -1001234567890


@dataclass
class Harness:
    service: ModerationService
    articles: SqlArticleRepository
    themes: SqlThemeRepository
    publications: SqlPublicationRepository
    fetcher: FakeFetcher
    summarizer: FakeSummarizer
    publisher: FakePublisher

    def add_theme(
        self,
        *,
        title: str = "Django",
        slug: str = "django",
    ) -> Theme:
        return self.themes.add(Theme(title=title, slug=slug))


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("Тест попытался открыть сетевое соединение")

    monkeypatch.setattr(socket, "create_connection", fail)


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    database = tmp_path / "moderation.sqlite3"
    upgrade_temp_sqlite(database)
    engine, factory = open_session(sqlite_url(database))
    session = factory()
    articles = SqlArticleRepository(session)
    themes = SqlThemeRepository(session)
    publications = SqlPublicationRepository(session)
    fetcher = FakeFetcher()
    summarizer = FakeSummarizer()
    publisher = FakePublisher()
    service = ModerationService(
        articles,
        themes,
        publications,
        fetcher,
        summarizer,
        publisher,
        str(CHANNEL_CHAT_ID),
    )
    try:
        yield Harness(
            service,
            articles,
            themes,
            publications,
            fetcher,
            summarizer,
            publisher,
        )
    finally:
        session.close()
        engine.dispose()
