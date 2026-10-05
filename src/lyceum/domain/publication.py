from dataclasses import dataclass
from datetime import datetime

from lyceum.domain.errors import DomainError


@dataclass
class Publication:
    """Снимок отправки. После записи поля не меняются."""

    article_id: int
    telegram_chat_id: int
    telegram_message_id: int
    url: str
    published_at: datetime
    id: int | None = None

    def require_id(self) -> int:
        if self.id is None:
            raise DomainError('Публикация ещё не сохранена.')
        return self.id
