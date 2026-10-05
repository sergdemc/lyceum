import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import lyceum.infrastructure.db.session  # noqa: E402, F401  регистрирует PRAGMA foreign_keys
from lyceum.infrastructure.db.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def migration_url() -> str:
    """Тесты кладут путь к временному файлу в config.attributes.

    Этот путь важнее DATABASE_URL и sqlalchemy.url из ini, чтобы pytest
    не накатывал ревизию на рабочую базу. Команда alembic upgrade head
    без attributes берёт DATABASE_URL, если он задан, иначе ini.
    """
    forced = config.attributes.get('database_url')
    if isinstance(forced, str) and forced:
        return forced
    from_env = os.environ.get('DATABASE_URL')
    if from_env:
        return from_env
    return config.get_main_option('sqlalchemy.url')


def run_migrations_offline() -> None:
    context.configure(
        url=migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section['sqlalchemy.url'] = migration_url()
    connectable = engine_from_config(
        section,
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
