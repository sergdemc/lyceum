from dataclasses import dataclass

from lyceum.domain.errors import DomainError


@dataclass
class Theme:
    title: str
    slug: str
    id: int | None = None

    def require_id(self) -> int:
        if self.id is None:
            raise DomainError('Тема ещё не сохранена.')
        return self.id
