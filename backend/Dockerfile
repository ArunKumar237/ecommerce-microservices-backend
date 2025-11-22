FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app
COPY ./requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY . /app

# Create static dir
RUN mkdir -p /app/static /app/media

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
