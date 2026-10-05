class DomainError(Exception):
    """Нарушение правила предметной области."""


class ArticleNotFound(DomainError):
    def __init__(self, article_id: int) -> None:
        super().__init__(f'Статья {article_id} не найдена.')
        self.article_id = article_id


class ThemeNotFound(DomainError):
    def __init__(self, theme_id: int) -> None:
        super().__init__(f'Тема {theme_id} не найдена.')
        self.theme_id = theme_id


class FetchFailed(DomainError):
    def __init__(self, url: str) -> None:
        super().__init__(f'Не удалось скачать страницу: {url}')
        self.url = url
