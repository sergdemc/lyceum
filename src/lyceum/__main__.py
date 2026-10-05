import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from lyceum.application.moderation import ModerationService, ensure_starter_themes
from lyceum.config import Settings
from lyceum.handlers.moderation import build_moderation_router
from lyceum.infrastructure.db.repositories import (
    SqlArticleRepository,
    SqlPublicationRepository,
    SqlThemeRepository,
)
from lyceum.infrastructure.db.session import open_session
from lyceum.infrastructure.fetching import TrafilaturaFetcher
from lyceum.infrastructure.publishing import TelegramChannelPublisher
from lyceum.infrastructure.summarizing import build_summarizer


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('aiogram.client').setLevel(logging.WARNING)
    log = logging.getLogger('lyceum')
    settings = Settings()
    if not settings.telegram_bot_token:
        raise SystemExit('Не задан TELEGRAM_BOT_TOKEN.')
    if not settings.telegram_chat_id:
        raise SystemExit('Не задан TELEGRAM_CHAT_ID.')
    engine, factory = open_session(settings.database_url)
    session = factory()
    try:
        ensure_starter_themes(SqlThemeRepository(session))
    except Exception as exc:
        if 'no such table' in str(exc).lower():
            raise SystemExit('В базе нет таблиц. Выполните make migrate.') from exc
        raise
    finally:
        session.close()
    log.info('саммари=%s канал=%s', settings.summarizer, settings.telegram_chat_id)
    if settings.summarizer.strip() == 'cursor' and not settings.cursor_api_key.strip():
        log.warning('SUMMARIZER=cursor, но CURSOR_API_KEY пуст. Выжимка не построится.')

    def run(action):
        bound = factory()
        try:
            service = ModerationService(
                SqlArticleRepository(bound),
                SqlThemeRepository(bound),
                SqlPublicationRepository(bound),
                TrafilaturaFetcher(),
                build_summarizer(settings.summarizer, settings.cursor_api_key),
                TelegramChannelPublisher(
                    settings.telegram_bot_token,
                    settings.telegram_chat_id,
                ),
                settings.telegram_chat_id,
            )
            return action(service)
        finally:
            bound.close()

    async def polling() -> None:
        bot = Bot(token=settings.telegram_bot_token)
        dispatcher = Dispatcher()
        dispatcher.include_router(build_moderation_router(run))
        await bot.set_my_commands(
            [
                BotCommand(command='url', description='Ссылка на статью'),
                BotCommand(command='text', description='Чужой текст'),
                BotCommand(command='post', description='Готовый пост'),
                BotCommand(command='theme', description='Новая тема'),
            ]
        )
        log.info('long polling запущен')
        try:
            await dispatcher.start_polling(bot)
        finally:
            await bot.session.close()
            engine.dispose()

    asyncio.run(polling())


if __name__ == '__main__':
    main()
