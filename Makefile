.PHONY: up down build dev logs ps shell-api shell-db migrate seed test lint format install clean

# ── Environment ──────────────────────────────────────────────────────────────
ENV ?= development
COMPOSE = docker compose -f docker-compose.yml
API_CONTAINER = aurum-api
DB_CONTAINER  = aurum-postgres

# ── Lifecycle ─────────────────────────────────────────────────────────────────
up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

dev:
	$(COMPOSE) up

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

# ── Database ──────────────────────────────────────────────────────────────────
migrate:
	$(COMPOSE) exec $(API_CONTAINER) alembic upgrade head

migrate-create:
	$(COMPOSE) exec $(API_CONTAINER) alembic revision --autogenerate -m "$(msg)"

migrate-down:
	$(COMPOSE) exec $(API_CONTAINER) alembic downgrade -1

seed:
	$(COMPOSE) exec $(API_CONTAINER) python scripts/seed.py

# ── Development ───────────────────────────────────────────────────────────────
shell-api:
	$(COMPOSE) exec $(API_CONTAINER) bash

shell-db:
	$(COMPOSE) exec $(DB_CONTAINER) psql -U aurum -d aurum_commerce

# ── Quality ───────────────────────────────────────────────────────────────────
test:
	$(COMPOSE) exec $(API_CONTAINER) pytest tests/ -v

lint:
	$(COMPOSE) exec $(API_CONTAINER) ruff check .

format:
	$(COMPOSE) exec $(API_CONTAINER) ruff format .

# ── Local (no Docker) ────────────────────────────────────────────────────────
install:
	pip install -r requirements.txt

dev-local:
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# ── Agents ───────────────────────────────────────────────────────────────────
run-agent:
	python -m agents.$(agent).main

brief:
	python -m agents.executive_advisor.main --now

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete 2>/dev/null; \
	find . -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null; \
	echo "Cleaned."
