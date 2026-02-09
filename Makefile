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
	podman run --name db --network=litnet -e POSTGRES_PASSWORD=bookpassword -e POSTGRES_DB=bookdb -e POSTGRES_USER=bookuser -p 5432:5432 -d postgres 

start-api:
	podman build backend --no-cache -t fastapi:main  
	podman run --name backend --network=litnet -e DATABASE_URL=postgresql://bookuser:bookpassword@db:5432/bookdb -p 80:80 -d fastapi:main

start-backend:
	make create-db
	python -m backend.database
	make start-api
