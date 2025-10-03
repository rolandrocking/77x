.DEFAULT_GOAL := build

run-docker-compose-command:
	docker compose ${command}
dc: run-docker-compose-command

build-image: command=build mynudge_backend_suggestion
build-image: dc

run: command=up
run: dc

run-command:
	docker compose run --rm mynudge_backend_suggestion $(command)

migrate: command=alembic upgrade head
migrate: run-command

lint: command=flake8
lint: run-command

# tests
DB_NAME=suggestion_test_db
DB_USER=mynudge_backend_suggestion_db_user
DB_PASSWORD=mynudge_backend_suggestion_db_password
ADMIN_DB=postgres

exec-db = docker compose exec -T mynudge_backend_suggestion_postgres psql -U $(DB_USER) -d $(ADMIN_DB) -c

create-test-db:
	$(exec-db) "DROP DATABASE IF EXISTS $(DB_NAME);"
	$(exec-db) "CREATE DATABASE $(DB_NAME);"

drop-test-db:
	$(exec-db) "DROP DATABASE IF EXISTS $(DB_NAME);"

migrate-test-db:
	POSTGRES_DB=$(DB_NAME) docker compose run --rm mynudge_backend_suggestion alembic upgrade head

run-tests:
	POSTGRES_DB=$(DB_NAME) docker compose run --rm mynudge_backend_suggestion pytest tests/

tests: create-test-db migrate-test-db run-tests drop-test-db
