.DEFAULT_GOAL := help

.PHONY: help sync install test migrate run

help:
	@echo "make sync      uv sync: окружение, зависимости, uv.lock"
	@echo "make test      uv run pytest"
	@echo "make migrate   uv run alembic upgrade head в вашу базу"
	@echo "make run       uv run python -m lyceum"

sync:
	uv sync

install: sync

test:
	uv run pytest

migrate:
	mkdir -p data
	uv run alembic upgrade head

run:
	uv run python -m lyceum
