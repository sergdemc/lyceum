import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject

from lyceum.application.cards import NEW_THEME_ACTION, ModerationAction, ModerationCard
from lyceum.application.moderation import ModerationOutcome, ModerationService
from lyceum.domain.errors import DomainError

START_TEXT = 'Пришлите материал командой:\n/url https://…\n/text текст статьи\n/post готовый пост\n/theme название\n\n«Править» и «Новая тема» ждут следующее сообщение. После перезапуска бота это ожидание пропадает, пришлите его ещё раз.'
RESTART_NOTE = 'После перезапуска бота это ожидание пропадает.'

ServiceRun = Callable[[Callable[[ModerationService], object]], object]
logger = logging.getLogger('lyceum')


COLLECT_PAUSE_SECONDS = 1.5


def utf16_len(text: str) -> int:
    return len(text.encode('utf-16-le')) // 2


def append_part(buffer: str, part: str) -> str:
    cleaned = part.strip()
    if not cleaned:
        return buffer
    if not buffer:
        return cleaned
    return f'{buffer}\n{cleaned}'


def _short(text: str | None) -> str:
    if not text:
        return ''
    one_line = ' '.join(text.split())
    if len(one_line) <= 120:
        return one_line
    return one_line[:117] + '…'


def _logged(exc: BaseException) -> str:
    logger.warning('%s', exc)
    return str(exc)


class _LogUpdate(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict) -> object:
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            logger.info(
                'входящее chat=%s user=%s utf16=%s %s',
                event.chat.type,
                user_id,
                utf16_len(event.text or ''),
                _short(event.text),
            )
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            logger.info('кнопка user=%s data=%s', user_id, event.data)
        return await handler(event, data)


_LABELS = {
    ModerationAction.PUBLISH: 'Опубликовать',
    ModerationAction.SERIES: 'В серию',
    ModerationAction.REGENERATE: 'Переделать',
    ModerationAction.EDIT: 'Править',
    ModerationAction.REJECT: 'Отклонить',
}


class ModerationCallback(CallbackData, prefix='mod'):
    action: str
    article_id: int


class ThemeCallback(CallbackData, prefix='theme'):
    article_id: int
    theme_id: int


def render_card(card: ModerationCard) -> str:
    lines = [
        card.title,
        f'Источник: {card.source_label}',
        f'Тема: {card.theme_title}' if card.theme_title else 'Тема: не выбрана',
        '',
    ]
    if card.needs_text:
        lines.append(card.hint or '')
    else:
        lines.append(card.summary)
        if card.hint:
            lines.extend(['', card.hint])
    return '\n'.join(lines)


def moderation_keyboard(card: ModerationCard) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for action in card.actions:
        if action is ModerationAction.PUBLISH and not card.publish_available:
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    text=_LABELS[action],
                    callback_data=ModerationCallback(
                        action=action.value,
                        article_id=card.article_id,
                    ).pack(),
                )
            ]
        )
    for theme in card.themes:
        mark = '✓ ' if theme.selected else ''
        rows.append(
            [
                InlineKeyboardButton(
                    text=f'{mark}{theme.title}',
                    callback_data=ThemeCallback(
                        article_id=card.article_id,
                        theme_id=theme.id,
                    ).pack(),
                )
            ]
        )
    if card.actions:
        rows.append(
            [
                InlineKeyboardButton(
                    text='Новая тема',
                    callback_data=ModerationCallback(
                        action=NEW_THEME_ACTION,
                        article_id=card.article_id,
                    ).pack(),
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def outcome_for_action(service: ModerationService, action: str, article_id: int) -> ModerationOutcome:
    mapping = {
        ModerationAction.PUBLISH.value: service.approve,
        ModerationAction.SERIES.value: service.enqueue_series,
        ModerationAction.REGENERATE.value: service.regenerate,
        ModerationAction.REJECT.value: service.reject,
    }
    try:
        method = mapping[action]
    except KeyError as exc:
        raise DomainError(f'Неизвестное действие: {action}') from exc
    return method(article_id)


@dataclass
class _Wait:
    kind: str
    article_id: int | None = None
    buffer: str = ''
    token: int = 0


class _Drafts:
    """Ожидание следующего сообщения. Новый token отменяет прежнюю отправку в саммари."""

    def __init__(self) -> None:
        self._items: dict[int, _Wait] = {}
        self._clock = 0

    def remember(
        self,
        user_id: int | None,
        kind: str,
        article_id: int | None = None,
        buffer: str = '',
    ) -> int:
        if user_id is None:
            return 0
        self._clock += 1
        self._items[user_id] = _Wait(kind, article_id, buffer, self._clock)
        logger.info('жду следующее сообщение user=%s kind=%s article=%s', user_id, kind, article_id)
        return self._clock

    def forget(self, user_id: int | None) -> None:
        if user_id is None:
            return
        self._clock += 1
        self._items.pop(user_id, None)

    def get(self, user_id: int) -> _Wait | None:
        return self._items.get(user_id)

    def take(self, user_id: int, token: int) -> _Wait | None:
        wait = self._items.get(user_id)
        if wait is None or wait.token != token:
            return None
        self._items.pop(user_id, None)
        return wait


def _card_text(outcome: ModerationOutcome) -> str:
    text = render_card(outcome.card)
    if outcome.notice:
        text = f'{outcome.notice}\n\n{text}'
    if len(text) <= 4096:
        return text
    return text[:4093] + '…'


def build_moderation_router(run: ServiceRun) -> Router:
    """Личка оператора и кнопки карточки."""
    router = Router(name='moderation')
    router.message.middleware(_LogUpdate())
    router.callback_query.middleware(_LogUpdate())
    drafts = _Drafts()
    summary_lock = asyncio.Lock()
    running: set[asyncio.Task[None]] = set()

    def spawn(task: asyncio.Task[None]) -> None:
        running.add(task)
        task.add_done_callback(running.discard)

    def call(action: Callable[[ModerationService], ModerationOutcome]) -> ModerationOutcome:
        result = run(action)
        if not isinstance(result, ModerationOutcome):
            raise DomainError('Сценарий вернул не карточку.')
        return result

    async def execute(
        action: Callable[[ModerationService], ModerationOutcome],
        *,
        summarize: bool,
    ) -> ModerationOutcome:
        if not summarize:
            return await asyncio.to_thread(call, action)
        async with summary_lock:
            return await asyncio.to_thread(call, action)

    async def show_message(message: Message, outcome: ModerationOutcome) -> None:
        logger.info(
            'карточка article=%s status=%s notice=%s',
            outcome.article.id,
            outcome.article.status.value,
            outcome.notice or '',
        )
        await message.answer(_card_text(outcome), reply_markup=moderation_keyboard(outcome.card))

    async def show_query(query: CallbackQuery, outcome: ModerationOutcome) -> None:
        logger.info(
            'карточка article=%s status=%s notice=%s',
            outcome.article.id,
            outcome.article.status.value,
            outcome.notice or '',
        )
        toast = outcome.notice or 'Карточка обновлена.'
        if len(toast) > 180:
            toast = toast[:177] + '…'
        await query.answer(toast)
        if query.message is not None:
            await query.message.edit_text(
                _card_text(outcome),
                reply_markup=moderation_keyboard(outcome.card),
            )

    def remember(
        user_id: int | None,
        kind: str,
        article_id: int | None = None,
        buffer: str = '',
    ) -> int:
        return drafts.remember(user_id, kind, article_id, buffer)

    def forget(user_id: int | None) -> None:
        drafts.forget(user_id)

    async def finish_collected(message: Message, user_id: int, token: int, kind: str) -> None:
        await asyncio.sleep(COLLECT_PAUSE_SECONDS)
        wait = drafts.take(user_id, token)
        if wait is None or wait.kind != kind:
            return
        collected = wait.buffer
        logger.info('текст собран user=%s символов=%s', user_id, len(collected))
        try:
            if kind == 'text':
                outcome = await execute(
                    lambda service: service.submit_text(collected),
                    summarize=True,
                )
            else:
                outcome = await execute(
                    lambda service: service.submit_ready_post(collected),
                    summarize=False,
                )
        except (DomainError, RuntimeError) as exc:
            await message.answer(_logged(exc))
            return
        await show_message(message, outcome)

    @router.message(Command('start'), F.chat.type == 'private')
    async def on_start(message: Message) -> None:
        forget(message.from_user.id if message.from_user else None)
        await message.answer(START_TEXT)

    @router.message(Command('url'), F.chat.type == 'private')
    async def on_url(message: Message, command: CommandObject) -> None:
        forget(message.from_user.id if message.from_user else None)
        url = (command.args or '').strip()
        if not url:
            await message.answer('Пришлите ссылку: /url https://…')
            return
        try:
            outcome = await execute(lambda service: service.submit_url(url), summarize=True)
        except (DomainError, RuntimeError) as exc:
            await message.answer(_logged(exc))
            return
        await show_message(message, outcome)

    @router.message(Command('text'), F.chat.type == 'private')
    async def on_text_command(message: Message, command: CommandObject) -> None:
        user_id = message.from_user.id if message.from_user else None
        forget(user_id)
        body = (command.args or '').strip()
        if not body:
            remember(user_id, 'text')
            await message.answer('Пришлите текст статьи следующим сообщением.')
            return
        token = remember(user_id, 'text', buffer=body)
        logger.info('собираю текст user=%s символов=%s', user_id, len(body))
        if user_id is None:
            return
        spawn(asyncio.create_task(finish_collected(message, user_id, token, 'text')))

    @router.message(Command('post'), F.chat.type == 'private')
    async def on_post(message: Message, command: CommandObject) -> None:
        user_id = message.from_user.id if message.from_user else None
        forget(user_id)
        body = (command.args or '').strip()
        if not body:
            remember(user_id, 'post')
            await message.answer('Пришлите готовый пост следующим сообщением.')
            return
        token = remember(user_id, 'post', buffer=body)
        logger.info('собираю текст user=%s символов=%s', user_id, len(body))
        if user_id is None:
            return
        spawn(asyncio.create_task(finish_collected(message, user_id, token, 'post')))

    @router.message(Command('theme'), F.chat.type == 'private')
    async def on_theme_command(message: Message, command: CommandObject) -> None:
        forget(message.from_user.id if message.from_user else None)
        name = (command.args or '').strip()
        if not name:
            await message.answer('Пришлите название: /theme Redis')
            return
        try:
            notice = await asyncio.to_thread(lambda: run(lambda service: service.register_theme(name)))
        except (DomainError, RuntimeError) as exc:
            await message.answer(_logged(exc))
            return
        await message.answer(str(notice))

    @router.message(F.chat.type == 'private', F.text)
    async def on_followup(message: Message) -> None:
        text = message.text or ''
        if text.startswith('/'):
            return
        user_id = message.from_user.id if message.from_user else None
        if user_id is None:
            return
        wait = drafts.get(user_id)
        if wait is None:
            await message.answer('Не понял сообщение. Команды: /url, /text, /post, /theme.')
            return
        if wait.kind in {'text', 'post'} and wait.article_id is None:
            collected = append_part(wait.buffer, text)
            token = remember(user_id, wait.kind, buffer=collected)
            logger.info('дописываю текст user=%s символов=%s', user_id, len(collected))
            spawn(asyncio.create_task(finish_collected(message, user_id, token, wait.kind)))
            return
        forget(user_id)
        try:
            if wait.kind == 'edit' and wait.article_id is not None:
                article_id = wait.article_id
                outcome = await execute(
                    lambda service: service.edit_summary(article_id, text),
                    summarize=False,
                )
            elif wait.kind == 'theme' and wait.article_id is not None:
                article_id = wait.article_id
                outcome = await execute(
                    lambda service: service.attach_named_theme(article_id, text),
                    summarize=False,
                )
            else:
                await message.answer('Ожидание сброшено. Пришлите команду ещё раз.')
                return
        except (DomainError, RuntimeError) as exc:
            await message.answer(_logged(exc))
            return
        await show_message(message, outcome)

    @router.callback_query(ModerationCallback.filter())
    async def on_moderation(query: CallbackQuery, callback_data: ModerationCallback) -> None:
        user_id = query.from_user.id if query.from_user else None
        if callback_data.action == ModerationAction.EDIT.value:
            remember(user_id, 'edit', callback_data.article_id)
            await query.answer(f'Пришлите новый текст выжимки. {RESTART_NOTE}')
            return
        if callback_data.action == NEW_THEME_ACTION:
            remember(user_id, 'theme', callback_data.article_id)
            await query.answer(f'Пришлите название темы. {RESTART_NOTE}')
            return
        summarize = callback_data.action == ModerationAction.REGENERATE.value
        try:
            outcome = await execute(
                lambda service: outcome_for_action(
                    service,
                    callback_data.action,
                    callback_data.article_id,
                ),
                summarize=summarize,
            )
        except (DomainError, RuntimeError) as exc:
            await query.answer(_logged(exc)[:180])
            return
        await show_query(query, outcome)

    @router.callback_query(ThemeCallback.filter())
    async def on_theme(query: CallbackQuery, callback_data: ThemeCallback) -> None:
        try:
            outcome = await execute(
                lambda service: service.choose_theme(callback_data.article_id, callback_data.theme_id),
                summarize=False,
            )
        except (DomainError, RuntimeError) as exc:
            await query.answer(_logged(exc)[:180])
            return
        await show_query(query, outcome)

    return router
