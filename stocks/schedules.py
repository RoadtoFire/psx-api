from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    'update-daily-prices': {
        'task': 'stocks.tasks.update_daily_prices',
        'schedule': crontab(hour=16, minute=30, day_of_week='1-5'),
    },
    'update-index-prices': {
        'task': 'stocks.tasks.update_index_prices',
        'schedule': crontab(hour=16, minute=30, day_of_week='1-5'),
    },
    'update-dividends': {
        'task': 'stocks.tasks.update_dividends',
        'schedule': crontab(hour=17, minute=0, day_of_week='1-5'),
    },
    # Run every morning at 9 AM
    'process-ex-date-notifications': {
        'task': 'transactions.tasks.process_ex_date_notifications',
        'schedule': crontab(hour=9, minute=0, day_of_week='1-5'),
    },
}