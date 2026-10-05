from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ThemeRow(Base):
    __tablename__ = 'themes'
    __table_args__ = (UniqueConstraint('slug', name='uq_themes_slug'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80))


class ArticleRow(Base):
    __tablename__ = 'articles'
    __table_args__ = (
        Index('ix_articles_status', 'status'),
        Index('ix_articles_theme_id', 'theme_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    origin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    theme_id: Mapped[int | None] = mapped_column(
        ForeignKey('themes.id', name='fk_articles_theme_id'),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PublicationRow(Base):
    __tablename__ = 'publications'
    __table_args__ = (UniqueConstraint('article_id', name='uq_publications_article_id'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey('articles.id', name='fk_publications_article_id'))
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger)
    url: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
