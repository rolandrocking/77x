.DEFAULT_GOAL := build

run-docker-compose-command:
	docker compose ${command}
dc: run-docker-compose-command

build-image: command=build mynudge_backend_suggestion
build-image: dc

run: command=up
run: dc

run-command:
	docker compose run --rm 77x $(command)

migrate: command=alembic upgrade head
migrate: run-command

migrate-revision: command=alembic revision --autogenerate -m "$(message)"
migrate-revision: run-command

lint: command=flake8
lint: run-command
