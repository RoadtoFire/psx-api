# Amanat | امانت
#### Video Demo: (https://youtu.be/7kdBJh6AwE4)
#### Description:

Amanat (امانت — Urdu for *trust* and *safekeeping*) is a full-stack web application built for Pakistani Muslim investors who want to participate in the Pakistan Stock Exchange (PSX) while staying Shariah compliant. The application automates dividend purification calculations, tracks portfolios in real time, and screens stocks against the KMI All Shares Islamic Index — eliminating the need for manual spreadsheet calculations that most Pakistani Muslim investors currently rely on.

## The Problem

Pakistan has over 220,000 registered retail investors on the PSX. A significant portion of these investors follow Islamic finance principles, which means they are only permitted to invest in Shariah-compliant stocks — those that pass all 6 criteria of the KMI All Shares Islamic Index, developed jointly by the Pakistan Stock Exchange and Meezan Bank. Beyond stock selection, Islamic finance also requires investors to perform "purification" (تطہیر) — when a company earns even a small amount of income from non-permissible sources (under 5% of total revenue), the investor must donate the proportional amount of their dividend to charity. The purification ratio for each stock is published by Al-Meezan in semi-annual PDF recomposition reports. Before Amanat, investors had to manually cross-reference these PDFs, look up each stock's ratio, and calculate the amount themselves for every dividend received. Nobody was doing this consistently.

## Architecture

Amanat uses a decoupled architecture — a Django REST Framework backend that exposes a REST API, consumed by a React frontend. I chose this approach over a traditional Django monolith (with server-rendered templates) because it allows the frontend to be deployed independently on Vercel's global CDN, giving Pakistani users fast load times, while the backend runs on Railway. It also means the API can eventually serve a mobile app without any backend changes.

The backend is deployed on Railway and the frontend on Vercel. Authentication is handled with JWT tokens via the `djangorestframework-simplejwt` library. I chose JWT over Django's session-based authentication because the frontend is on a different domain than the backend, making cookie-based sessions impractical without complex CORS configuration.

## Backend Files

**`config/settings.py`** — Django settings file. Configures the database using `dj_database_url` to parse the `DATABASE_URL` environment variable provided by Railway, sets up Celery with Redis as the broker and result backend, and configures CORS to allow requests from the Vercel frontend domain.

**`config/celery.py`** — Celery application configuration. Initializes the Celery app and configures it to autodiscover tasks from all installed Django apps.

**`stocks/models.py`** — Defines the core data models: `Stock` (symbol, name, sector, logo URL), `StockPrice` (daily closing price per stock), and `Dividend` (dividend events with ex-date, amount, and purification ratio).

**`stocks/tasks.py`** — Contains the Celery tasks that run on a schedule: `update_daily_prices` scrapes end-of-day prices from the PSX data portal, `update_index_prices` updates index-level data, and `update_dividends` checks for new dividend announcements and updates the database if new records are found.

**`stocks/schedules.py`** — Defines the Celery Beat schedule using crontab expressions. Prices are updated at 4:30 PM PKT on weekdays (after market close), dividends at 5:00 PM PKT, and ex-date notifications at 9:00 AM PKT — all Monday to Friday only, since the PSX does not trade on weekends.

**`stocks/views.py`** — DRF ViewSets for the stocks API. Provides endpoints to list all stocks, retrieve a single stock by symbol, and filter by sector.

**`transactions/models.py`** — Defines the `Transaction` model which stores a user's buy/sell history — stock symbol, shares, price, and date. Portfolio calculations are derived from these records.

**`transactions/views.py`** — API views for portfolio management: calculating current portfolio value and P&L by joining transaction history with live prices, calculating dividend income with tax deductions (15% for filers, 30% for non-filers), computing purification amounts per dividend event, and marking purifications as complete.

**`transactions/tasks.py`** — Contains the `process_ex_date_notifications` task that checks each morning whether any stocks a user holds have an upcoming ex-date, triggering a notification.

**`users/models.py`** — Custom user model extending Django's `AbstractBaseUser`. Adds `filer_status` (filer or non-filer) and `whatsapp_number` fields. I chose a custom user model rather than extending the default with a profile model because Django recommends this at the start of a project — changing it later requires database migrations that can be very disruptive.

**`scraper.py`** — A standalone Python script used to do the initial bulk scrape of historical stock prices from `dps.psx.com.pk` using the `requests` library. This populated the database with approximately 340,000 daily price records covering years of historical data for all 285 Shariah-compliant stocks.

**`dividend_scraper.py`** — A standalone script that scraped historical dividend data from SCS Trade, populating approximately 2,800 dividend events across all covered stocks.

**`purification_parser.py`** — Parses the Al-Meezan KMI recomposition PDF reports to extract purification ratios for each stock. The PDFs are semi-annual and contain the ratio of non-compliant income for every stock in the index. This script extracts those ratios and inserts them into the database, linking each ratio to the correct stock and the date range it applies to.

**`start.sh`** — Shell script used as the Railway start command. It runs Django migrations, starts Gunicorn as the WSGI server, and launches the Celery worker with beat scheduler using the `solo` pool. I chose the solo pool over the default prefork pool because Railway containers run as root, and Celery's prefork concurrency model has known issues with broken pipe errors in root-privileged containers.

## Frontend

The React frontend is built with Vite and styled with Tailwind CSS v4. It communicates with the backend exclusively via the REST API using Axios. An Axios interceptor automatically attaches the JWT access token to every request and handles token refresh on 401 responses — so users stay logged in across sessions without needing to re-authenticate.

The frontend has six main pages: a public landing page, login and registration pages, and four protected pages (Dashboard, Portfolio, Dividends, Stocks, and Learn) wrapped in a `ProtectedRoute` component that checks authentication state before rendering.

## Design Decisions

**PostgreSQL over SQLite** — While SQLite would have been sufficient for development, I chose PostgreSQL for production because multiple users will be querying the same stock price data simultaneously. PostgreSQL handles concurrent reads and writes more reliably, and Railway provides managed PostgreSQL with automatic backups.

**Celery over cron jobs** — I could have used a simple Linux cron job to run the scraper scripts. I chose Celery with django-celery-beat instead because it integrates with Django's ORM, stores the schedule in the database (making it configurable without code changes), and provides task result tracking and retry logic out of the box.

**Decoupled architecture** — Separating the frontend from the backend adds deployment complexity but provides flexibility. The React app can be hosted on Vercel's CDN for fast global delivery, and the API can be versioned and extended independently. It also made the PWA implementation straightforward — the frontend is a standalone installable web app that works like a native mobile app on iOS and Android.

## Database

| Table | Records |
|-------|---------|
| Shariah compliant stocks | 285 |
| Daily price records | ~340,000 |
| Dividend events | ~2,800 |
| Purification ratios | ~765 |
| Stock logos | 283 |

## Live Demo

**App:** https://amanat-psx.vercel.app
**API Docs:** https://trustworthy-spontaneity-production-61c4.up.railway.app/api/docs/
**Backend Repo:** https://github.com/RoadtoFire/psx-api

---

*"Amanat — because your wealth is a trust."*
