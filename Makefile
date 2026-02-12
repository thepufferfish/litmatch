# Project Constants
ENV_FILE=.env
COMPOSE=podman compose --env-file $(ENV_FILE)
COMPOSE_TEST=podman compose -f compose.yaml -f compose.test.yaml --env-file $(ENV_FILE) -p litmatch-test

# Podman Compose Commands
up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

backend-shell:
	$(COMPOSE) exec backend bash

db-shell:
	$(COMPOSE) exec db psql -U $$(grep POSTGRES_USER $(ENV_FILE) | cut -d '=' -f2) -d $$(grep POSTGRES_DB $(ENV_FILE) | cut -d '=' -f2)

# Scrapy via Scrapyd
run-spider:
	curl http://localhost:6800/schedule.json -d project=bookmarks -d spider=bookmarks

# Dagster
dagster-logs:
	$(COMPOSE) logs -f dagster-code dagster-webserver dagster-daemon

# Cleanup
clean:
	$(COMPOSE) down -v

# Rebuild Everything
rebuild:
	$(COMPOSE) down -v
	$(COMPOSE) up --build --force-recreate -d

create-db:
	podman run --name db --network=litnet \
		-e POSTGRES_PASSWORD=$$(grep POSTGRES_PASSWORD $(ENV_FILE) | cut -d '=' -f2) \
		-e POSTGRES_DB=$$(grep POSTGRES_DB $(ENV_FILE) | cut -d '=' -f2) \
		-e POSTGRES_USER=$$(grep POSTGRES_USER $(ENV_FILE) | cut -d '=' -f2) \
		-p 5432:5432 -d postgres

start-api:
	podman build backend --no-cache -t fastapi:main
	podman run --name backend --network=litnet --env-file $(ENV_FILE) -p 80:8000 -d fastapi:main

start-frontend:
	podman build frontend --no-cache -t litmatch-frontend:local
	podman run --name frontend --network=litnet -p 8080:80 -d litmatch-frontend:local

stop-frontend:
	podman stop frontend && podman rm frontend

start-backend:
	make create-db
	python -m backend.database
	make start-api

start-all:
	make start-backend
	make start-frontend

# Testing
test-unit:
	uv run pytest tests/dagster/ -v -m "not integration"

test-integration:
	$(COMPOSE_TEST) up --build -d
	uv run pytest tests/integration/ -v -m integration --tb=short; \
	EXIT_CODE=$$?; \
	$(COMPOSE_TEST) down -v; \
	exit $$EXIT_CODE

test-integration-up:
	$(COMPOSE_TEST) up --build -d

test-integration-down:
	$(COMPOSE_TEST) down -v

test-all:
	make test-unit
	make test-integration

test-coverage:
	uv run pytest tests/dagster/ -v --cov=litmatch --cov-report=term-missing -m "not integration"
