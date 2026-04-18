web: python manage.py migrate && gunicorn config.wsgi
worker: celery -A config worker --beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler