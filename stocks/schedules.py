from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    # Run Monday-Friday at 4:30 PM Karachi time (after market closes at 3:30 PM)
    'update-daily-prices': {
        'task': 'stocks.tasks.update_daily_prices',
        'schedule': crontab(hour=16, minute=30, day_of_week='1-5'),
    },
    'update-index-prices': {
        'task': 'stocks.tasks.update_index_prices',
        'schedule': crontab(hour=16, minute=30, day_of_week='1-5'),
    },
    # Check for new dividends every day at 5 PM
    'update-dividends': {
        'task': 'stocks.tasks.update_dividends',
        'schedule': crontab(hour=17, minute=0, day_of_week='1-5'),
    },
}