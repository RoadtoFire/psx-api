#!/bin/bash
set -e

echo "Running migrations..."
python manage.py migrate

echo "Starting Gunicorn..."
gunicorn config.wsgi --bind 0.0.0.0:$PORT &

echo "Starting Celery worker + beat..."
celery -A config worker --beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler &

wait