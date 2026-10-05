from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from lyceum.domain.article import Article
from lyceum.domain.errors import ArticleNotFound, ThemeNotFound
from lyceum.domain.publication import Publication
from lyceum.domain.status import ArticleSource, ArticleStatus
from lyceum.domain.theme import Theme
from lyceum.infrastructure.db.models import ArticleRow, PublicationRow, ThemeRow


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _blank_to_none(value: str) -> str | None:
    return value if value else None


def to_theme(row: ThemeRow) -> Theme:
    return Theme(
        id=row.id,
        title=row.title,
        slug=row.slug,
    )


def to_article(row: ArticleRow) -> Article:
    return Article(
        id=row.id,
        source=ArticleSource(row.source),
        status=ArticleStatus(row.status),
        origin_url=row.origin_url,
        title=row.title or '',
        raw_text=row.raw_text or '',
        summary=row.summary or '',
        theme_id=row.theme_id,
        created_at=_as_utc(row.created_at),
    )


def to_publication(row: PublicationRow) -> Publication:
    return Publication(
        id=row.id,
        article_id=row.article_id,
        telegram_chat_id=row.telegram_chat_id,
        telegram_message_id=row.telegram_message_id,
        url=row.url,
        published_at=_as_utc(row.published_at),
    )


class SqlThemeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, theme: Theme) -> Theme:
        row = ThemeRow(title=theme.title, slug=theme.slug)
        self._session.add(row)
        self._session.commit()
        theme.id = row.id
        return theme

    def get(self, theme_id: int) -> Theme:
        row = self._session.get(ThemeRow, theme_id)
        if row is None:
            raise ThemeNotFound(theme_id)
        return to_theme(row)

    def find_by_slug(self, slug: str) -> Theme | None:
        row = self._session.scalar(select(ThemeRow).where(ThemeRow.slug == slug))
        if row is None:
            return None
        return to_theme(row)

    def save(self, theme: Theme) -> Theme:
        theme_id = theme.require_id()
        row = self._session.get(ThemeRow, theme_id)
        if row is None:
            raise ThemeNotFound(theme_id)
        row.title = theme.title
        row.slug = theme.slug
        self._session.commit()
        return theme

    def list_all(self) -> list[Theme]:
        rows = self._session.scalars(select(ThemeRow).order_by(ThemeRow.id)).all()
        return [to_theme(row) for row in rows]


class SqlArticleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, article: Article) -> Article:
        row = self._row_from_article(article)
        self._session.add(row)
        self._session.commit()
        article.id = row.id
        return article

    def get(self, article_id: int) -> Article:
        row = self._session.get(ArticleRow, article_id)
        if row is None:
            raise ArticleNotFound(article_id)
        return to_article(row)

    def save(self, article: Article) -> Article:
        article_id = article.require_id()
        row = self._session.get(ArticleRow, article_id)
        if row is None:
            raise ArticleNotFound(article_id)
        self._copy(article, row)
        self._session.commit()
        return article

    def _row_from_article(self, article: Article) -> ArticleRow:
        return ArticleRow(
            source=article.source.value,
            origin_url=article.origin_url,
            title=_blank_to_none(article.title),
            raw_text=_blank_to_none(article.raw_text),
            summary=_blank_to_none(article.summary),
            theme_id=article.theme_id,
            status=article.status.value,
            created_at=article.created_at,
        )

    def _copy(self, article: Article, row: ArticleRow) -> None:
        row.source = article.source.value
        row.origin_url = article.origin_url
        row.title = _blank_to_none(article.title)
        row.raw_text = _blank_to_none(article.raw_text)
        row.summary = _blank_to_none(article.summary)
        row.theme_id = article.theme_id
        row.status = article.status.value
        row.created_at = article.created_at


class SqlPublicationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, publication: Publication) -> Publication:
        row = PublicationRow(
            article_id=publication.article_id,
            telegram_chat_id=publication.telegram_chat_id,
            telegram_message_id=publication.telegram_message_id,
            url=publication.url,
            published_at=publication.published_at,
        )
        self._session.add(row)
        self._session.commit()
        publication.id = row.id
        return publication

    def get_by_article(self, article_id: int) -> Publication | None:
        row = self._session.scalar(select(PublicationRow).where(PublicationRow.article_id == article_id))
        if row is None:
            return None
        return to_publication(row)
