from pathlib import Path

from alembic import command
from alembic.config import Config

from lyceum.infrastructure.db.session import sqlite_url

ROOT = Path(__file__).resolve().parents[1]


def upgrade_temp_sqlite(path: Path) -> None:
    """Накатывает ревизию только на переданный файл, не на sqlalchemy.url из ini."""
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    url = sqlite_url(path)
    cfg.attributes["database_url"] = url
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
