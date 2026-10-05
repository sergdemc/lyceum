#!/usr/bin/env python3
"""Cursor beforeShellExecution hook: Python commands go through uv.

Allows `uv run`, `uv sync`, `make test|sync|install`, or an explicit `.venv`.
Fail-open for unknown shell shapes.
"""

from __future__ import annotations

import json
import re
import sys

ALLOW = [
    r'(^|[;&|]\s*)uv\s+run\b',
    r'(^|[;&|]\s*)uv\s+sync\b',
    r'(^|[;&|]\s*)uv\s+add\b',
    r'(^|[;&|]\s*)uv\s+lock\b',
    r'(^|[;&|]\s*)make\s+(?:test|sync|install|help)\b',
]

DENY = [
    (
        r'(^|[;&|]\s*)pytest\b',
        'Тесты запускай через `make test` или `uv run pytest`.',
    ),
    (
        r'(^|[;&|]\s*)python(?:3)?\s+-m\s+pytest\b',
        'Тесты запускай через `make test` или `uv run pytest`.',
    ),
    (
        r'(^|[;&|]\s*)pip(?:3)?\s+(?:install|uninstall|freeze|check|list)\b',
        'Зависимости ставь через `uv add` и `make sync`, не через pip.',
    ),
    (
        r'(^|[;&|]\s*)alembic\b',
        'Alembic вызывай через `uv run alembic`. Накатывать ревизию на базу нельзя: это делает пользователь.',
    ),
]


def command_from(data: dict) -> str:
    command = data.get('command')
    if command:
        return str(command)
    tool_input = data.get('tool_input') or {}
    if isinstance(tool_input, dict):
        return str(tool_input.get('command', ''))
    return ''


def allow() -> int:
    print(json.dumps({'permission': 'allow'}))
    return 0


def deny(message: str) -> int:
    print(
        json.dumps(
            {
                'permission': 'deny',
                'user_message': message,
                'agent_message': message,
            },
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return allow()

    cmd = command_from(data)
    if not cmd:
        return allow()

    if '.venv/bin/' in cmd or re.search(r'(?:source|\.)\s+\.venv/bin/activate', cmd):
        return allow()

    if any(re.search(pattern, cmd, flags=re.IGNORECASE) for pattern in ALLOW):
        return allow()

    for pattern, message in DENY:
        if re.search(pattern, cmd, flags=re.IGNORECASE):
            return deny(message)

    return allow()


if __name__ == '__main__':
    raise SystemExit(main())
