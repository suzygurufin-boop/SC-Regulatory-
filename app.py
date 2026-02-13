from flask import Flask, jsonify, request, render_template_string
import feedparser
import json
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus, urlparse
import pandas as pd
from flask import send_file
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo

def get_last_updated():
    if CACHE["timestamp"] == 0:
        return "Not fetched yet"

    dt = datetime.fromtimestamp(
        CACHE["timestamp"],
        ZoneInfo("Asia/Seoul")  # since you're in Korea
    )
    return dt.strftime("%Y-%m-%d %H:%M:%S KST")

CACHE = {
    "data": None,
    "timestamp": 0
}

CACHE_DURATION = 600  # seconds (10 minutes)

try:
	import tldextract
except Exception:
	tldextract = None

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
	<meta charset="utf-8" />
	<meta name="viewport" content="width=device-width, initial-scale=1" />
	<title>Stablecoin Regulatory News — Last 24h</title>
	<style>
	  body { font-family: Arial, Helvetica, sans-serif; margin: 24px; }
	  .item { padding: 12px 0; border-bottom: 1px solid #eee; }
	  .meta { color: #666; font-size: 0.9em; }
	</style>
  </head>
  <body>
	<h1>Stablecoin Regulatory News — Last 24 hours</h1>
	<p><a href="/fetch">Run fetch now</a> · <a href="/api/news">JSON API</a> · <a href="/news-table">Table View</a></p>
	{% if items %}
	  {% for it in items %}
		<div class="item">
		  <div class="meta"><strong>{{ it.country }}</strong> · {{ it.published }}</div>
		  <div class="title"><a href="{{ it.link }}" target="_blank" rel="noopener">{{ it.title }}</a></div>
		</div>
	  {% endfor %}
	{% else %}
	  <p>No items found for the last 24 hours.</p>
	{% endif %}
  </body>
</html>
"""

TABLE_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
	<meta charset="utf-8" />
	<meta name="viewport" content="width=device-width, initial-scale=1" />
	<title>Stablecoin Regulatory News — Table View</title>
	<style>
	  body { 
		font-family: Arial, Helvetica, sans-serif; 
		margin: 24px; 
		background-color: #f5f5f5;
	  }
	  h1 { color: #333; }
	  .controls { margin-bottom: 20px; }
	  .controls a { 
		display: inline-block;
		padding: 8px 16px; 
		background-color: #0066cc; 
		color: white; 
		text-decoration: none; 
		border-radius: 4px;
		margin-right: 10px;
	  }
	  .controls a:hover { background-color: #0052a3; }
	  table {
		width: 100%;
		border-collapse: collapse;
		background-color: white;
		box-shadow: 0 2px 4px rgba(0,0,0,0.1);
		border-radius: 4px;
		overflow: hidden;
	  }
	  thead {
		background-color: #0066cc;
		color: white;
	  }
	  th {
		padding: 12px 16px;
		text-align: left;
		font-weight: bold;
		border-bottom: 2px solid #0066cc;
	  }
	  td {
		padding: 12px 16px;
		border-bottom: 1px solid #eee;
	  }
	  tr:hover {
		background-color: #f9f9f9;
	  }
	  .country {
		font-weight: bold;
		color: #0066cc;
		background-color: #e6f2ff;
		padding: 4px 8px;
		border-radius: 3px;
		display: inline-block;
	  }
	  .published {
		color: #666;
		font-size: 0.9em;
	  }
	  .title-link {
		color: #0066cc;
		text-decoration: none;
		font-weight: 500;
	  }
	  .title-link:hover {
		text-decoration: underline;
	  }
	  .no-items {
		padding: 40px;
		text-align: center;
		color: #999;
		background-color: white;
		border-radius: 4px;
	  }
	  .item-count {
		color: #666;
		margin-bottom: 20px;
		font-size: 0.95em;
	  }
	</style>
  </head>
  <body>
	<h1>Stablecoin Regulatory News — Table View</h1>

	<div style="margin-bottom:15px; color:gray; font-size:14px;">
    Last auto fetch: {{ last_updated }}
</div>

	<div class="controls">
	  <a href="/">Home</a>
	  <a href="/fetch">Run Fetch</a>
	  <a href="/api/news">JSON API</a>
	  <a href="/download-excel">Download Excel</a>
	</div>
	
	{% if items %}
	  <div class="item-count">Showing <strong>{{ items|length }}</strong> items from the last 24 hours</div>
	  <table>
		<thead>
		  <tr>
			<th style="width: 12%;">Country</th>
			<th style="width: 50%;">Title</th>
			<th style="width: 20%;">Published</th>
			<th style="width: 18%;">Source</th>
		  </tr>
		</thead>
		<tbody>
		  {% for item in items %}
			<tr>
			  <td>
				<span class="country">{{ item.country }}</span>
			  </td>
			  <td>
				<a href="{{ item.link }}" target="_blank" rel="noopener" class="title-link">
				  {{ item.title }}
				</a>
			  </td>
			  <td>
				<span class="published">{{ item.published.replace('T',' ')[:16] }}</span>
			  </td>
			  <td>
				<small>{{ item.link[:40] }}...</small>
			  </td>
			</tr>
		  {% endfor %}
		</tbody>
	  </table>
	  <div style="margin-top:20px;">
  {% if page > 1 %}
    <a href="/news-table?page={{ page-1 }}">Previous</a>
  {% endif %}

  Page {{ page }} of {{ total_pages }}

  {% if page < total_pages %}
    <a href="/news-table?page={{ page+1 }}">Next</a>
  {% endif %}
</div>
	{% else %}
	  <div class="no-items">
		<p>No items found for the last 24 hours.</p>
		<p><a href="/fetch" style="color: #0066cc;">Run fetch now</a> to get started.</p>
	  </div>
	{% endif %}
  </body>
</html>
"""

def _now_utc():
	return datetime.now(timezone.utc)


COUNTRIES = [
	"United States", "US", "United Kingdom", "UK", "Canada", "Australia", "Singapore",
	"Hong Kong", "China", "Japan", "South Korea", "Korea", "India", "Brazil", "Mexico",
	"Germany", "France", "Italy", "Spain", "Netherlands", "Sweden", "Norway", "Switzerland",
	"Russia", "Turkey", "Argentina", "Chile", "Colombia"
]

def get_news():
    now = time.time()

    # if exists and not expired
   if CACHE["data"] and (now - CACHE["timestamp"] < CACHE_DURATION):
        return CACHE["data"]

    # otherwise fetch new data
    data = fetch_news()
    CACHE["data"] = data
    CACHE["timestamp"] = now

    return data
	
def detect_country(entry):
	text = " ".join(filter(None, [entry.get("title", ""), entry.get("summary", "")]))
	text_lower = text.lower()
	for c in COUNTRIES:
		if c.lower() in text_lower:
			return c

	link = entry.get("link", "")
	if link:
		if tldextract is not None:
			try:
				ext = tldextract.extract(link)
				suffix = ext.suffix
				if suffix and len(suffix) == 2:
					return suffix.upper()
			except Exception:
				pass
		else:
			# fallback: try to parse hostname and take last label as country code (best-effort)
			try:
				h = urlparse(link).hostname or ""
				parts = h.split('.')
				if parts:
					last = parts[-1]
					if len(last) == 2:
						return last.upper()
			except Exception:
				pass

	return "Unknown"


def fetch_google_news_rss(query, region="US"):
	q = quote_plus(query)
	url = f"https://news.google.com/rss/search?q={q}%20when:7d&hl=en-{region}&gl={region}&ceid={region}:en"
	try:
		return feedparser.parse(url)
	except Exception:
		return None


def canonicalize_item(entry):
	if "published_parsed" in entry and entry.published_parsed:
		published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

	else:
		published = _now_utc()

	title = entry.get("title", "(no title)")
	link = entry.get("link", "")
	country = detect_country(entry)

	return {
		"country": country,
		"title": title,
		"published": published.isoformat(),
		"link": link,
	}


def fetch_news():
    queries = [
        "stablecoin regulation",
        "stablecoin announcement",
        "stablecoin guidance",
        "stablecoin law",
        "stablecoin ban",
        "stablecoin oversight",
    ]

    items = []
    seen_links = set()
    now = _now_utc()
    cutoff = now - timedelta(hours=24)

    for q in queries:
        feed = fetch_google_news_rss(q)
        if not feed or not getattr(feed, "entries", None):
            continue

        for entry in feed.entries:
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            else:
                published = now

            if published < cutoff:
                continue

            link = entry.get("link", "")
            if not link or link in seen_links:
                continue

            seen_links.add(link)
            items.append(canonicalize_item(entry))

    items.sort(key=lambda x: x.get("published", ""), reverse=True)
    return items

@app.route("/")
def index():
    items = get_news()
    return render_template_string(
        TEMPLATE,
        items=items
    )

@app.route("/news-table")
def news_table():
    page = int(request.args.get("page", 1))
    per_page = 50

    items = get_news()
    total = len(items)

    start = (page - 1) * per_page
    end = start + per_page
    paginated_items = items[start:end]

    total_pages = (total + per_page - 1) // per_page

    return render_template_string(
    TABLE_TEMPLATE,
    items=paginated_items,
    page=page,
    total_pages=total_pages,
    last_updated=get_last_updated()
)


@app.route("/api/news")
def api_news():
	items = get_news()
	return jsonify(items)


@app.route("/fetch")
def manual_fetch_route():
    data = fetch_news()

    CACHE["data"] = data
    CACHE["timestamp"] = time.time()

    page = 1
    per_page = 50
    total = len(data)

    paginated_items = data[:per_page]
    total_pages = (total + per_page - 1) // per_page

    return render_template_string(
    TABLE_TEMPLATE,
    items=paginated_items,
    page=page,
    total_pages=total_pages,
    last_updated=get_last_updated()
)


@app.route("/download-excel")
def download_excel():
    items = get_news()
    if not items:
        return "No data available", 400

    df = pd.DataFrame(items)

    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="stablecoin_news.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )










