"""Themes, articles and publications.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-04

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = '0001_initial'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'themes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=80), nullable=False),
        sa.UniqueConstraint('slug', name='uq_themes_slug'),
    )
    op.create_table(
        'articles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source', sa.String(length=32), nullable=False),
        sa.Column('origin_url', sa.Text(), nullable=True),
        sa.Column('title', sa.String(length=300), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('theme_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['theme_id'], ['themes.id'], name='fk_articles_theme_id'),
    )
    op.create_index('ix_articles_status', 'articles', ['status'])
    op.create_index('ix_articles_theme_id', 'articles', ['theme_id'])
    op.create_table(
        'publications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('telegram_chat_id', sa.BigInteger(), nullable=False),
        sa.Column('telegram_message_id', sa.BigInteger(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], name='fk_publications_article_id'),
        sa.UniqueConstraint('article_id', name='uq_publications_article_id'),
    )


def downgrade() -> None:
    op.drop_table('publications')
    op.drop_index('ix_articles_theme_id', table_name='articles')
    op.drop_index('ix_articles_status', table_name='articles')
    op.drop_table('articles')
    op.drop_table('themes')
