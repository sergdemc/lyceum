from urllib.parse import urlparse

import httpx
import trafilatura

from lyceum.domain.errors import FetchFailed
from lyceum.domain.protocols import FetchedPage

_HEADERS = {'User-Agent': 'lyceum/0.1'}


class TrafilaturaFetcher:
    """Скачивает страницу через httpx и достаёт текст через trafilatura.

    Сценарии этого среза в тестах получают другую реализацию ArticleFetcher.
    """

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def fetch(self, url: str) -> FetchedPage:
        parsed = urlparse(url)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            raise FetchFailed(url)
        try:
            html = self._download(url)
        except httpx.HTTPError as exc:
            raise FetchFailed(url) from exc
        text = trafilatura.extract(html, url=url, include_comments=False) or ''
        metadata = trafilatura.extract_metadata(html, default_url=url)
        title = metadata.title if metadata is not None else None
        return FetchedPage(text=text, title=title)

    def _download(self, url: str) -> str:
        if self._client is not None:
            response = self._client.get(url)
            response.raise_for_status()
            return response.text
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=_HEADERS) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text
