from dataclasses import dataclass, field
from datetime import datetime, timezone

from lyceum.domain.errors import DomainError
from lyceum.domain.status import ArticleSource, ArticleStatus
from lyceum.domain.text import is_usable_article_text


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Article:
    source: ArticleSource
    status: ArticleStatus = ArticleStatus.RECEIVED
    origin_url: str | None = None
    title: str = ''
    raw_text: str = ''
    summary: str = ''
    theme_id: int | None = None
    created_at: datetime = field(default_factory=_utcnow)
    id: int | None = None

    def require_id(self) -> int:
        if self.id is None:
            raise DomainError('Статья ещё не сохранена.')
        return self.id

    def needs_manual_text(self) -> bool:
        if self.status not in {ArticleStatus.RECEIVED, ArticleStatus.EXTRACTED}:
            return False
        if self.source is ArticleSource.READY_POST:
            return self.raw_text.strip() == ''
        return not is_usable_article_text(self.raw_text)

    def set_title(self, title: str) -> None:
        cleaned = title.strip()
        if cleaned:
            self.title = cleaned[:300]

    def replace_body(self, *, title: str | None, raw_text: str) -> None:
        if self.status not in {ArticleStatus.RECEIVED, ArticleStatus.EXTRACTED}:
            raise DomainError('Текст можно записать только до модерации.')
        if title and title.strip():
            self.title = title.strip()[:300]
        self.raw_text = raw_text.strip()
        self.status = ArticleStatus.EXTRACTED

    def mark_awaiting_review(self, summary: str) -> None:
        if self.status not in {
            ArticleStatus.RECEIVED,
            ArticleStatus.EXTRACTED,
            ArticleStatus.AWAITING_REVIEW,
        }:
            raise DomainError('На модерацию нельзя отправить статью в этом статусе.')
        cleaned = summary.strip()
        if not cleaned:
            raise DomainError('Пустая выжимка.')
        self.summary = cleaned
        self.status = ArticleStatus.AWAITING_REVIEW

    def assign_theme(self, theme_id: int) -> None:
        if self.status is not ArticleStatus.AWAITING_REVIEW:
            raise DomainError('Тему можно выбрать только на модерации.')
        self.theme_id = theme_id

    def edit_summary(self, summary: str) -> None:
        if self.status is not ArticleStatus.AWAITING_REVIEW:
            raise DomainError('Править можно только выжимку на модерации.')
        cleaned = summary.strip()
        if not cleaned:
            raise DomainError('Пустая выжимка.')
        self.summary = cleaned

    def reject(self) -> None:
        if self.status is not ArticleStatus.AWAITING_REVIEW:
            raise DomainError('Отклонить можно только статью на модерации.')
        self.status = ArticleStatus.REJECTED

    def mark_published(self) -> None:
        if self.status is not ArticleStatus.AWAITING_REVIEW:
            raise DomainError('Опубликовать можно только статью на модерации.')
        if self.theme_id is None:
            raise DomainError('Сначала выберите тему.')
        self.status = ArticleStatus.PUBLISHED
