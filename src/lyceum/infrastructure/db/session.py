import sqlite3
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def sqlite_url(path: Path) -> str:
    return 'sqlite:///' + path.resolve().as_posix()


@event.listens_for(Engine, 'connect')
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.close()


def open_session(url: str) -> tuple[Engine, sessionmaker[Session]]:
    engine = create_engine(url)
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    return engine, factory
