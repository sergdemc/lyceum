#!/usr/bin/env python3
"""Cursor beforeShellExecution hook for Lyceum.

Blocks destructive git commands and applying Alembic to a database.
Fail-open on hook parsing failures.
"""

from __future__ import annotations

import json
import re
import sys

BLOCK = [
    (r'(^|[;&|]\s*)git\s+reset\s+--hard\b', 'Не используй git reset --hard: можно потерять незакоммиченные изменения.'),
    (r'(^|[;&|]\s*)git\s+clean\s+[^;&|]*-[^;&|]*f', 'Не используй git clean -f без явного решения пользователя.'),
    (r'(^|[;&|]\s*)git\s+checkout\s+--\s+\.\s*($|[;&|])', 'Не сбрасывай весь working tree через git checkout -- .'),
    (r'(^|[;&|]\s*)git\s+restore\s+\.\s*($|[;&|])', 'Не сбрасывай весь working tree через git restore .'),
    (r'(^|[;&|]\s*)make\s+migrate\b', 'make migrate меняет базу. Команду запускает пользователь.'),
    (r'\balembic\s+upgrade\b', 'alembic upgrade меняет базу. Команду запускает пользователь.'),
    (r'\balembic\s+downgrade\b', 'alembic downgrade меняет базу. Команду запускает пользователь.'),
    (r'\balembic\s+stamp\b', 'alembic stamp меняет состояние миграций в базе. Команду запускает пользователь.'),
]


def command_from(data: dict) -> str:
    command = data.get('command')
    if command:
        return str(command)
    tool_input = data.get('tool_input') or {}
    if isinstance(tool_input, dict):
        return str(tool_input.get('command', ''))
    return ''


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        print(json.dumps({'permission': 'allow'}))
        return 0

    command = command_from(data)
    for pattern, message in BLOCK:
        if re.search(pattern, command, flags=re.IGNORECASE):
            print(
                json.dumps(
                    {
                        'permission': 'deny',
                        'user_message': message,
                        'agent_message': message + ' Выбери безопасный способ и сохрани текущие изменения.',
                    },
                    ensure_ascii=False,
                )
            )
            return 0

    print(json.dumps({'permission': 'allow'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
