from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from lyceum.domain.article import Article
from lyceum.domain.publication import Publication
from lyceum.domain.theme import Theme


@dataclass(frozen=True)
class FetchedPage:
    text: str
    title: str | None = None


@dataclass(frozen=True)
class OutboundPost:
    article_id: int
    telegram_chat_id: str
    text: str


@dataclass(frozen=True)
class PublishReceipt:
    telegram_chat_id: int
    telegram_message_id: int
    url: str


class ArticleRepository(Protocol):
    def add(self, article: Article) -> Article: ...

    def get(self, article_id: int) -> Article: ...

    def save(self, article: Article) -> Article: ...


class ThemeRepository(Protocol):
    def add(self, theme: Theme) -> Theme: ...

    def get(self, theme_id: int) -> Theme: ...

    def find_by_slug(self, slug: str) -> Theme | None: ...

    def save(self, theme: Theme) -> Theme: ...

    def list_all(self) -> Sequence[Theme]: ...


class PublicationRepository(Protocol):
    def add(self, publication: Publication) -> Publication: ...

    def get_by_article(self, article_id: int) -> Publication | None: ...


class ArticleFetcher(Protocol):
    def fetch(self, url: str) -> FetchedPage: ...


class Summarizer(Protocol):
    def summarize(self, text: str, *, title: str | None = None) -> str: ...


class Publisher(Protocol):
    def publish(self, post: OutboundPost) -> PublishReceipt: ...
