# Project Constants
ENV_FILE=.env
COMPOSE=docker compose --env-file $(ENV_FILE)

# Docker Compose Commands
# up:
# 	$(COMPOSE) up --build -d

# down:
# 	$(COMPOSE) down

# logs:
# 	$(COMPOSE) logs -f

# backend-shell:
# 	$(COMPOSE) exec backend bash

# db-shell:
# 	$(COMPOSE) exec db psql -U $$(grep POSTGRES_USER $(ENV_FILE) | cut -d '=' -f2) -d $$(grep POSTGRES_DB $(ENV_FILE) | cut -d '=' -f2)

# # Scrapy via Scrapyd
# run-spider:
# 	curl http://localhost:6800/schedule.json -d project=bookmarks -d spider=bookmarks

# # ETL (Assumes mounted volume with books.jsonl)
# run-etl:
# 	docker compose run --rm etl python etl_runner.py

# # Recommender (if integrated)
# run-recommender:
# 	docker compose run --rm etl python recommender/hybrid_engine.py

# # Cleanup
# clean:
# 	$(COMPOSE) down -v

# # Rebuild Everything
# rebuild:
# 	$(COMPOSE) down -v
# 	$(COMPOSE) up --build -d

create-db:
	docker run --name db --network=litnet -e POSTGRES_PASSWORD=bookpassword -e POSTGRES_DB=bookdb -e POSTGRES_USER=bookuser -p 5432:5432 -d postgres 

start-api:
	docker build backend --no-cache -t fastapi:main  
	docker run --name backend --network=litnet -e DATABASE_URL=postgresql://bookuser:bookpassword@db:5432/bookdb -p 80:80 -d fastapi:main

start-backend:
	make create-db
	python -m backend.database
	make start-api
