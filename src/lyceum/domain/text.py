# Стена логина и пустая выдача короче нормальной статьи.
# Это порог длины, не классификатор страницы.
MIN_USABLE_TEXT_CHARS = 400
FORUM_TEXT_LIMIT = 4096


def is_usable_article_text(text: str) -> bool:
    return len(text.strip()) >= MIN_USABLE_TEXT_CHARS


def title_from_text(text: str, *, limit: int = 300) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:limit]
    return 'Без заголовка'


def split_summary(text: str) -> tuple[str | None, str]:
    """Первая строка «Заголовок: …» становится заголовком карточки, остальное — выжимкой."""
    cleaned = text.strip()
    if not cleaned:
        return None, ''
    first, _, rest = cleaned.partition('\n')
    prefix = 'Заголовок:'
    if not first.startswith(prefix):
        return None, cleaned
    title = first[len(prefix) :].strip()[:300]
    body = rest.strip()
    if not title or not body:
        return None, cleaned
    return title, body
