.PHONY: up down migrate createsuperuser logs

up:
	cd compose && docker-compose up --build -d

down:
	cd compose && docker-compose down

migrate:
	docker-compose exec web python manage.py migrate

createsuperuser:
	docker-compose exec web python manage.py createsuperuser

logs:
	docker-compose logs -f
