.PHONY: help db-up db-down db-reset stack-up stack-down \
  backend-install backend-dev backend-test backend-lint backend-format \
  frontend-install frontend-dev frontend-test frontend-lint frontend-format \
  test lint format

COMPOSE ?= docker compose -f gis-server/docker-compose.yml

help:
	@echo "Common targets:"
	@echo "  db-up             Start PostGIS only"
	@echo "  db-down           Stop PostGIS"
	@echo "  db-reset          Recreate PostGIS volume"
	@echo "  stack-up          Start full stack (db + backend + frontend)"
	@echo "  stack-down        Stop full stack"
	@echo "  backend-install   Install backend deps"
	@echo "  backend-dev       Run backend dev server"
	@echo "  backend-test      Run backend tests"
	@echo "  backend-lint      Run backend lint"
	@echo "  backend-format    Format backend code"
	@echo "  frontend-install  Install frontend deps"
	@echo "  frontend-dev      Run frontend dev server"
	@echo "  frontend-test     Run frontend tests"
	@echo "  frontend-lint     Run frontend lint"
	@echo "  frontend-format   Format frontend code"
	@echo "  test              Run backend + frontend tests"
	@echo "  lint              Run backend + frontend lint"
	@echo "  format            Format backend + frontend"

db-up:
	$(COMPOSE) up -d db

db-down:
	$(COMPOSE) down

db-reset:
	$(COMPOSE) down -v
	$(COMPOSE) up -d db

stack-up:
	$(COMPOSE) up -d --build

stack-down:
	$(COMPOSE) down

backend-install:
	cd gis-server && uv sync --extra dev

backend-dev:
	cd gis-server && uv run uvicorn main:app --reload --port 8000

backend-test:
	$(MAKE) -C gis-server test

backend-lint:
	$(MAKE) -C gis-server lint

backend-format:
	$(MAKE) -C gis-server format

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-test:
	cd frontend && npm run test

frontend-lint:
	cd frontend && npm run lint

frontend-format:
	cd frontend && npm run format

test: backend-test frontend-test

lint: backend-lint frontend-lint

format: backend-format frontend-format
