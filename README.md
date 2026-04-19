# Amanat | امانت
### Pakistan's first Shariah-compliant portfolio tracker

[![Live Demo](https://img.shields.io/badge/Live-amanat--psx.vercel.app-emerald)](https://amanat-psx.vercel.app)
[![Backend](https://img.shields.io/badge/API-Railway-purple)](https://trustworthy-spontaneity-production-61c4.up.railway.app/api/docs/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

#### Video Demo: (https://youtu.be/7kdBJh6AwE4)
#### Description:
Amanat is a free web app that automates Shariah-compliant portfolio tracking and dividend purification calculations for Pakistani Muslim investors on the Pakistan Stock Exchange. Built with Django REST Framework and React, it scrapes live PSX data, calculates dividend income with automatic tax deductions, and computes Islamic purification amounts using official Al-Meezan KMI recomposition ratios — eliminating the need for manual spreadsheet calculations.
---

No spreadsheets. No manual calculations. Just add your transactions and Amanat handles everything.

---

## Features

### 📊 Portfolio Tracking
- Track buy/sell transactions across all 285 KMI All Shares Islamic Index stocks
- Real-time P&L per holding based on latest PSX prices
- Cost basis vs current value breakdown

### 💰 Dividend Calculator
- Complete dividend history for every stock you hold
- Automatic tax deduction — 15% for filers, 30% for non-filers
- Yearly breakdown with bar chart visualization

### 🌙 Shariah Purification
- Automatic purification amounts calculated per dividend event
- Based on official Al-Meezan KMI recomposition ratios (updated every 6 months)
- One-click "mark as purified" to track your charity giving

### 🕌 Shariah Compliance Education
- Clear explanation of all 6 KMI screening criteria
- Embedded Investkaar Urdu video course for new investors
- Key concepts glossary (ex-date, book closure, bonus shares, etc.)

### 📈 Stock Browser
- All 285 Shariah compliant PSX stocks with logos
- Filter by sector (Cement, Chemical, Fertilizer, etc.)
- Stock detail modal with dividend history and purification rate

---

## Tech Stack

### Backend
| Technology | Purpose |
|-----------|---------|
| Django 6 + DRF | REST API |
| PostgreSQL | Database |
| Redis + Celery | Background tasks |
| JWT Auth | Authentication |
| Railway | Deployment |

### Frontend
| Technology | Purpose |
|-----------|---------|
| React + Vite | UI framework |
| Tailwind CSS v4 | Styling |
| Recharts | Data visualization |
| Lucide React | Icons |
| Vercel | Deployment |

### Data Sources
| Source | Data |
|--------|------|
| PSX (dps.psx.com.pk) | Stock symbols, EOD prices |
| SCS Trade | Dividend history |
| Al-Meezan KMI PDFs | Purification ratios |
| TradingView S3 | Stock logos |

---

## Database

| Table | Records |
|-------|---------|
| Shariah compliant stocks | 285 |
| Daily price records | ~340,000 |
| Dividend events | ~2,800 |
| Purification ratios | ~765 |
| Stock logos | 283 |

---

## API

ull Swagger documentation available at:
https://trustworthy-spontaneity-production-61c4.up.railway.app/api/docs/

Key endpoints:
POST /api/v1/auth/register/
POST /api/v1/auth/login/
GET  /api/v1/stocks/
GET  /api/v1/stocks/{symbol}/
GET  /api/v1/portfolio/value/
GET  /api/v1/portfolio/dividends/
POST /api/v1/portfolio/purification/mark/

---

## Local Development

### Backend
```bash
git clone https://github.com/RoadtoFire/psx-api
cd psx-api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # configure your environment
python manage.py migrate
python manage.py runserver
```

### Frontend
```bash
git clone https://github.com/RoadtoFire/psx-frontend
cd psx-frontend
npm install
cp .env.example .env.local  # set VITE_API_URL
npm run dev
```

---

## Automated Tasks (Celery)

| Task | Schedule |
|------|---------|
| Update daily stock prices | Weekdays 4:30 PM PKT |
| Update index prices | Weekdays 4:30 PM PKT |
| Update dividend data | Weekdays 5:00 PM PKT |
| Ex-date notifications | Weekdays 9:00 AM PKT |

---

## Roadmap

- [ ] PWA — installable on Android
- [ ] Push notifications for ex-dates
- [ ] WhatsApp alerts for upcoming dividends
- [ ] Portfolio performance vs KMI index chart
- [ ] React Native mobile app

---

## Contributing

Pull requests welcome. For major changes please open an issue first.

---

## Disclaimer

Amanat is a personal finance tool. It does not provide investment advice. Always do your own research before investing. Shariah compliance screening is based on PSX KMI All Shares Islamic Index — consult a qualified Islamic finance scholar for personal religious guidance.

---
*"Amanat — because your wealth is a trust."*


Full Swagger documentation available at:
