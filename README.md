# Stablecoin Regulatory News Collector

This single-file Flask app collects "stablecoin" regulatory news from Google News RSS searches and shows items published in the last 24 hours.

Quick start (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install flask feedparser tldextract beautifulsoup4 requests pytz
python srs1.py
```

Then open `http://localhost:5000`.

Endpoints:
- `/` — HTML page listing collected items (country, publish date, title)
- `/api/news` — JSON list
- `/fetch` — trigger a manual fetch

Deployment notes:
- To deploy publicly, push this repo to GitHub then create a Python web service on Render/Heroku.
- Use `gunicorn srs1:app` as the start command on the host and install `gunicorn` in requirements.
- Choose a domain like `stablecoin-regs.example.com` and set a CNAME to the host's assigned domain.
