from pathlib import Path

from sqlalchemy import inspect

from lyceum.infrastructure.db.session import open_session, sqlite_url
from tests.support import ROOT, upgrade_temp_sqlite


def test_upgrade_creates_channel_schema(tmp_path: Path) -> None:
    database = tmp_path / "schema.sqlite3"
    upgrade_temp_sqlite(database)
    engine, _factory = open_session(sqlite_url(database))
    try:
        inspector = inspect(engine)
        names = set(inspector.get_table_names())
        theme_columns = {column["name"] for column in inspector.get_columns("themes")}
        publication_columns = {column["name"] for column in inspector.get_columns("publications")}
    finally:
        engine.dispose()
    assert "topics" not in names
    assert {"themes", "articles", "publications", "alembic_version"} <= names
    assert theme_columns == {"id", "title", "slug"}
    assert publication_columns == {
        "id",
        "article_id",
        "telegram_chat_id",
        "telegram_message_id",
        "url",
        "published_at",
    }
    assert database.resolve() != (ROOT / "data" / "lyceum.db").resolve()


def test_upgrade_ignores_database_url_env(tmp_path: Path, monkeypatch) -> None:
    sentinel = tmp_path / "sentinel.sqlite3"
    monkeypatch.setenv("DATABASE_URL", sqlite_url(sentinel))
    target = tmp_path / "actual.sqlite3"
    upgrade_temp_sqlite(target)
    assert target.exists()
    assert not sentinel.exists()
