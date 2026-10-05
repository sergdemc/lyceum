"""Саммари через cursor-sdk.

SUMMARIZER=cursor вызывает облачного агента без репозитория.
Сценарии флаг не читают: адаптер выбирается снаружи.
Не клиент /v1/chat/completions и не httpx-прокси.
"""

from cursor_sdk import Agent, AgentOptions, CloudAgentOptions, CursorAgentError

from lyceum.domain.protocols import Summarizer

_MODEL = 'composer-2.5'


class CursorSummarizer:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key.strip()

    def summarize(self, text: str, *, title: str | None = None) -> str:
        if not self._api_key:
            raise RuntimeError('Не задан CURSOR_API_KEY. Саммари не построено.')
        try:
            result = Agent.prompt(
                _prompt(text, title),
                AgentOptions(
                    api_key=self._api_key,
                    model=_MODEL,
                    cloud=CloudAgentOptions(repos=[]),
                ),
            )
        except CursorAgentError as exc:
            raise RuntimeError('Не удалось получить саммари.') from exc
        summary = result.result.strip()
        if result.status != 'finished' or not summary:
            raise RuntimeError('Саммари не получено.')
        return summary


class UnavailableSummarizer:
    def summarize(self, text: str, *, title: str | None = None) -> str:
        del text, title
        raise RuntimeError('Саммари не подключено. Задайте SUMMARIZER=cursor.')


def build_summarizer(kind: str, api_key: str) -> Summarizer:
    cleaned = kind.strip()
    if cleaned == 'cursor':
        return CursorSummarizer(api_key)
    if cleaned == 'fake':
        return UnavailableSummarizer()
    raise RuntimeError(f'Неизвестный SUMMARIZER: {cleaned}')


def _prompt(text: str, title: str | None) -> str:
    heading = title.strip() if title and title.strip() else ''
    lines = [
        'Сделай выжимку статьи на русском языке для поста в Telegram.',
        'Первая строка строго в виде: Заголовок: короткий русский заголовок.',
        'После пустой строки — сама выжимка.',
        'Переведи весь текст на русский, включая начало статьи.',
        'Имена методов, полей и куски кода оставь как в оригинале.',
        'Раскрой основные приёмы и примеры так, чтобы пост читался без статьи.',
        'Если приёмов несколько, расскажи каждый. Не сжимай всё в один абзац.',
        'Уложись в 3500 знаков. Верни только заголовок и выжимку, без пояснений и без правок файлов.',
        '',
    ]
    if heading:
        lines.append(f'Оригинальный заголовок, его нужно перевести: {heading}')
        lines.append('')
    lines.append(text.strip())
    return '\n'.join(lines)
