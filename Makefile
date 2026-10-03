.PHONY: setup up down migrations migrate tests

setup:
	@test -f .env || cp .env.example .env
	uv sync
	uv run python src/manage.py tailwind setup

up:
	docker compose -f development.yaml up -d --build

down:
	docker compose -f development.yaml down

migrations:
	docker compose -f development.yaml exec web uv run --no-sync python src/manage.py makemigrations

migrate:
	docker compose -f development.yaml exec web uv run --no-sync python src/manage.py migrate

tests:
	docker compose -f development.yaml exec web \
		env -u DJANGO_SETTINGS_MODULE \
		uv run --no-sync pytest; \
		code=$$?; \
		[ $$code -eq 0 ] || [ $$code -eq 5 ]
