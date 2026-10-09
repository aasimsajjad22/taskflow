.PHONY: up down logs migrate migrations superuser shell test lint format

up:
    docker compose up --build -d

down:
    docker compose down

logs:
    docker compose logs -f web

migrate:
    docker compose exec web python manage.py migrate

migrations:
    docker compose exec web python manage.py makemigrations

superuser:
    docker compose exec web python manage.py createsuperuser

shell:
    docker compose exec web python manage.py shell

test:
    docker compose exec web pytest

lint:
    ruff check .

format:
    ruff format . && ruff check . --fix