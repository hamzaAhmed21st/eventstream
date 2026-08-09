SHELL := /bin/sh

UV ?= uv
PNPM ?= pnpm
COMPOSE ?= docker compose

SEED_API_URL ?= http://localhost:8000
SEED_COUNT ?= 100
SEED_RATE ?= 10
SEED_SERVICES ?= checkout,catalog,accounts
SEED_RANDOM ?= 42
TEST_DATABASE_URL ?= postgresql+psycopg://eventstream:eventstream@localhost:5432/eventstream_test
TEST_REDIS_URL ?= redis://localhost:6379/15

.DEFAULT_GOAL := help

.PHONY: help setup up down logs migrate test test-services test-backend \
	test-frontend lint typecheck seed verify frontend-build compose-config

help:
	@echo "EventStream development commands"
	@echo "  make setup          Install backend and frontend dependencies"
	@echo "  make up             Build and start the Compose stack"
	@echo "  make down           Stop the stack without deleting volumes"
	@echo "  make logs           Follow service logs"
	@echo "  make migrate        Apply Alembic migrations"
	@echo "  make test           Run backend and frontend tests"
	@echo "  make lint           Run backend and frontend linters"
	@echo "  make typecheck      Run Python and TypeScript type checks"
	@echo "  make seed           Send unique events with seeded metric content"
	@echo "  make verify         Run all non-destructive quality gates"

setup:
	$(UV) sync --locked
	$(PNPM) --dir frontend install --frozen-lockfile

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down --remove-orphans

logs:
	$(COMPOSE) logs --follow --tail=100

migrate:
	$(UV) run alembic upgrade head

test: test-backend test-frontend

test-services:
	$(COMPOSE) up -d --wait postgres redis
	@TEST_DATABASE_URL="$(TEST_DATABASE_URL)" \
		$(UV) run python scripts/prepare_test_database.py
	@DATABASE_URL="$(TEST_DATABASE_URL)" $(UV) run alembic upgrade head

test-backend: test-services
	@TEST_DATABASE_URL="$(TEST_DATABASE_URL)" \
		TEST_REDIS_URL="$(TEST_REDIS_URL)" \
		$(UV) run pytest

test-frontend:
	$(PNPM) --dir frontend test

lint:
	$(UV) run ruff check backend scripts
	$(PNPM) --dir frontend lint

typecheck:
	$(UV) run mypy backend scripts
	$(PNPM) --dir frontend typecheck

seed:
	$(UV) run python scripts/generate_events.py \
		--api-url "$(SEED_API_URL)" \
		--count "$(SEED_COUNT)" \
		--events-per-second "$(SEED_RATE)" \
		--services "$(SEED_SERVICES)" \
		--seed "$(SEED_RANDOM)"

frontend-build:
	$(PNPM) --dir frontend build

compose-config:
	$(COMPOSE) config --quiet

verify: lint typecheck test frontend-build compose-config
	@echo "All configured non-destructive verification checks passed."
