web: gunicorn config.wsgi --log-file -
worker: celery -A config worker --loglevel=info
beat: celery -A config beat --loglevel=info --scheduler 
django_celery_beat.schedulers:DatabaseSchedul