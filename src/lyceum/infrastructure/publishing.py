"""Отправка в канал через Bot API.

Long polling здесь не запускается. message_thread_id не передаётся.
"""

import logging

import httpx

from lyceum.domain.protocols import OutboundPost, PublishReceipt

logger = logging.getLogger('lyceum.publish')


def channel_message_url(chat_id: int, message_id: int, username: str | None) -> str:
    if username:
        return f'https://t.me/{username}/{message_id}'
    tail = str(chat_id)
    if tail.startswith('-100'):
        tail = tail[4:]
    return f'https://t.me/c/{tail}/{message_id}'


class TelegramChannelPublisher:
    def __init__(self, bot_token: str, chat_id: str, client: httpx.Client | None = None) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._client = client

    def publish(self, post: OutboundPost) -> PublishReceipt:
        if not self._bot_token:
            raise RuntimeError('Не задан TELEGRAM_BOT_TOKEN. Сообщение не отправлено.')
        logger.info('sendMessage chat_id=%s символов=%s', self._chat_id, len(post.text))
        response = self._post({'chat_id': self._chat_id, 'text': post.text})
        data = response.json()
        if not data.get('ok'):
            logger.error('Telegram отклонил sendMessage: %s', data.get('description'))
            raise RuntimeError('Telegram не принял сообщение.')
        result = data['result']
        message_id = int(result['message_id'])
        chat = result['chat']
        chat_id = int(chat['id'])
        username = chat.get('username') or None
        logger.info('опубликовано chat=%s message_id=%s', chat_id, message_id)
        return PublishReceipt(
            telegram_chat_id=chat_id,
            telegram_message_id=message_id,
            url=channel_message_url(chat_id, message_id, username),
        )

    def _post(self, payload: dict[str, str]) -> httpx.Response:
        url = f'https://api.telegram.org/bot{self._bot_token}/sendMessage'
        try:
            if self._client is not None:
                response = self._client.post(url, json=payload)
            else:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(url, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError('Не удалось отправить сообщение в канал.') from exc
        return response
