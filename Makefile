.PHONY: help db-up db-down db-reset stack-up stack-down stack-up-all \
  mlflow-up mlflow-down mlflow-logs \
  promote-baseline promote-hgt mlflow-leaderboard \
  dagger-ci dagger-ci-backend dagger-ci-frontend \
  backend-install backend-dev backend-test backend-lint backend-format \
  frontend-install frontend-dev frontend-test frontend-lint frontend-format \
  test lint format

COMPOSE ?= docker compose -f gis-server/docker-compose.yml

help:
	@echo "Common targets:"
	@echo "  db-up             Start PostGIS only"
	@echo "  db-down           Stop PostGIS"
	@echo "  db-reset          Recreate PostGIS volume"
	@echo "  stack-up          Start app stack (db + backend + frontend)"
	@echo "  stack-up-all      Start app stack + MLflow services"
	@echo "  stack-down        Stop full stack"
	@echo "  mlflow-up         Start MLflow (Postgres backend + local artifact volume)"
	@echo "  mlflow-down       Stop MLflow services"
	@echo "  mlflow-logs       Tail MLflow server logs"
	@echo "  promote-baseline  Promote baseline run (RUN_ID=...) with strict gate"
	@echo "  promote-hgt       Promote HGT run (RUN_ID=...) with strict gate"
	@echo "  mlflow-leaderboard Export MLflow leaderboard (METRIC=..., MODE=min|max)"
	@echo "  dagger-ci         Run Dagger pilot CI (backend + frontend)"
	@echo "  dagger-ci-backend Run Dagger backend CI function"
	@echo "  dagger-ci-frontend Run Dagger frontend CI function"
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
	$(COMPOSE) up -d --build db backend frontend

stack-up-all:
	$(COMPOSE) up -d --build

stack-down:
	$(COMPOSE) down

mlflow-up:
	$(COMPOSE) up -d --build mlflow-db mlflow

mlflow-down:
	$(COMPOSE) stop mlflow mlflow-db

mlflow-logs:
	$(COMPOSE) logs -f mlflow

promote-baseline:
	$(MAKE) -C gis-server promote-baseline RUN_ID=$(RUN_ID)

promote-hgt:
	$(MAKE) -C gis-server promote-hgt RUN_ID=$(RUN_ID)

mlflow-leaderboard:
	$(MAKE) -C gis-server mlflow-leaderboard METRIC=$(METRIC) MODE=$(MODE)

dagger-ci:
	dagger call ci-all --silent

dagger-ci-backend:
	dagger call ci-backend --silent

dagger-ci-frontend:
	dagger call ci-frontend --silent

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
