# Project Constants
ENV_FILE=.env
COMPOSE=podman compose --env-file $(ENV_FILE)

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
	$(COMPOSE) up --build -d

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
