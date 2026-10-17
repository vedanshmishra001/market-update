from __future__ import annotations

import csv
import io
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SNAPSHOT_FILE = DATA_DIR / "snapshots.csv"
NEWS_FILE = DATA_DIR / "news.csv"
REPORT_FILE = DATA_DIR / "latest_report.md"

# This prototype uses yfinance as an optional/unofficial retrieval adapter.
# Before publicly redistributing quotes or publishing them at scale, confirm
# rights/terms for your intended use and replace this adapter with a licensed source.
MARKETS = [
    {"symbol": "^NSEI", "name": "Nifty 50", "group": "India indices"},
    {"symbol": "^BSESN", "name": "Sensex", "group": "India indices"},
    {"symbol": "^NSEBANK", "name": "Nifty Bank", "group": "India indices"},
    {"symbol": "^GSPC", "name": "S&P 500", "group": "US indices"},
    {"symbol": "^IXIC", "name": "Nasdaq Composite", "group": "US indices"},
    {"symbol": "^DJI", "name": "Dow Jones", "group": "US indices"},
    {"symbol": "GC=F", "name": "Gold futures", "group": "Commodities"},
    {"symbol": "SI=F", "name": "Silver futures", "group": "Commodities"},
    {"symbol": "CL=F", "name": "WTI crude futures", "group": "Commodities"},
    {"symbol": "BZ=F", "name": "Brent crude futures", "group": "Commodities"},
    {"symbol": "INR=X", "name": "USD/INR indicative", "group": "Currencies"},
    {"symbol": "DX-Y.NYB", "name": "US Dollar Index", "group": "Currencies"},
]

NEWS_QUERIES = [
    ("India markets", "India stock market Nifty Sensex economy"),
    ("US markets", "US stock market S&P 500 Nasdaq Federal Reserve"),
    ("Commodities", "gold silver crude oil commodities market"),
    ("Global macro", "inflation central bank interest rates global economy"),
]

HEADERS = {"User-Agent": "DailyMarketPulse/1.0 (personal research dashboard)"}


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def fetch_prices():
    """Fetch latest available daily bars. Fails per symbol rather than stopping the run."""
    rows = []
    try:
        import yfinance as yf
    except Exception as exc:
        return rows, [f"yfinance import failed: {exc}"]

    errors = []
    for item in MARKETS:
        try:
            ticker = yf.Ticker(item["symbol"])
            hist = ticker.history(period="10d", interval="1d", auto_adjust=False)
            if hist is None or hist.empty:
                errors.append(f"No price data for {item['name']} ({item['symbol']})")
                continue
            hist = hist.dropna(subset=["Close"])
            if hist.empty:
                errors.append(f"No closing prices for {item['name']}")
                continue
            last = hist.iloc[-1]
            close = float(last["Close"])
            prev = float(hist.iloc[-2]["Close"]) if len(hist) > 1 else None
            change = ((close / prev) - 1) * 100 if prev else None
            date_value = pd.Timestamp(hist.index[-1]).date().isoformat()
            rows.append({
                "date": date_value,
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "symbol": item["symbol"],
                "name": item["name"],
                "group": item["group"],
                "close": close,
                "previous_close": prev,
                "change_pct": change,
                "source": "Yahoo Finance via yfinance (unofficial adapter)",
            })
        except Exception as exc:
            errors.append(f"{item['name']}: {type(exc).__name__}: {exc}")
        time.sleep(0.15)
    return rows, errors


def fetch_news():
    """Read Google News RSS headlines; store links to publishers and RSS-provided dates."""
    rows = []
    errors = []
    seen = set()
    for category, query in NEWS_QUERIES:
        url = "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=en-IN&gl=IN&ceid=IN:en"
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                source_el = item.find("source")
                source = (source_el.text or "").strip() if source_el is not None else "Google News RSS"
                if not title or not link or link in seen:
                    continue
                seen.add(link)
                try:
                    published = parsedate_to_datetime(pub).isoformat() if pub else ""
                except Exception:
                    published = pub
                rows.append({
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "category": category,
                    "title": title,
                    "source": source,
                    "published": published,
                    "url": link,
                })
        except Exception as exc:
            errors.append(f"News feed '{category}' failed: {type(exc).__name__}: {exc}")
    rows.sort(key=lambda r: r.get("published", ""), reverse=True)
    return rows, errors


def append_rows(path: Path, rows: list[dict], unique_keys: list[str]):
    if not rows:
        return 0
    df_new = pd.DataFrame(rows)
    if path.exists():
        try:
            df_old = pd.read_csv(path)
        except Exception:
            df_old = pd.DataFrame()
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new
    if unique_keys:
        existing_keys = [k for k in unique_keys if k in df.columns]
        if existing_keys:
            df = df.drop_duplicates(subset=existing_keys, keep="last")
    df.to_csv(path, index=False)
    return len(df_new)


def run_update():
    ensure_data_dir()
    messages = []
    price_rows, price_errors = fetch_prices()
    if price_rows:
        append_rows(SNAPSHOT_FILE, price_rows, ["date", "symbol"])
        messages.append(f"Saved {len(price_rows)} market observations.")
    else:
        messages.append("No market prices were saved. Check provider availability or terms.")
    news_rows, news_errors = fetch_news()
    if news_rows:
        append_rows(NEWS_FILE, news_rows, ["url"])
        messages.append(f"Saved/updated {len(news_rows)} headlines.")
    else:
        messages.append("No news headlines were saved.")
    messages.extend(price_errors[:8])
    messages.extend(news_errors[:4])
    try:
        snapshots = load_snapshots()
        news = load_news()
        post = build_linkedin_post(snapshots, news)
        REPORT_FILE.write_text(post, encoding="utf-8")
        messages.append("Generated latest LinkedIn draft.")
    except Exception as exc:
        messages.append(f"Report generation issue: {exc}")
    return messages


def load_snapshots():
    if not SNAPSHOT_FILE.exists():
        return pd.DataFrame(columns=[
            "date", "retrieved_at_utc", "symbol", "name", "group",
            "close", "previous_close", "change_pct", "source"
        ])
    try:
        df = pd.read_csv(SNAPSHOT_FILE)
        for col in ["close", "previous_close", "change_pct"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def load_news():
    if not NEWS_FILE.exists():
        return pd.DataFrame(columns=["category", "title", "source", "published", "url"])
    try:
        return pd.read_csv(NEWS_FILE).fillna("")
    except Exception:
        return pd.DataFrame()


def fmt_price(value):
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return "N/A"


def fmt_change(value):
    try:
        value = float(value)
        return f"{value:+.2f}%"
    except Exception:
        return "N/A"


def build_linkedin_post(snapshots: pd.DataFrame, news: pd.DataFrame) -> str:
    today = datetime.now().strftime("%d %b %Y")
    lines = [
        f"DAILY MARKET PULSE | {today}",
        "",
        "Markets at a glance",
    ]
    if snapshots.empty:
        lines += ["Market data is not available in the saved dataset yet."]
    else:
        snapshots = snapshots.copy()
        snapshots["date"] = pd.to_datetime(snapshots["date"], errors="coerce")
        latest_date = snapshots["date"].max()
        latest = snapshots[snapshots["date"] == latest_date]
        for group in ["India indices", "US indices", "Commodities", "Currencies"]:
            group_df = latest[latest["group"] == group]
            if group_df.empty:
                continue
            lines.append(f"\n{group}:")
            for _, row in group_df.iterrows():
                lines.append(f"• {row['name']}: {fmt_price(row['close'])} ({fmt_change(row['change_pct'])})")

    lines += ["", "Headlines to watch"]
    if news.empty:
        lines.append("• No headlines saved. Check the news feed before publishing.")
    else:
        for _, row in news.head(5).iterrows():
            title = re.sub(r"\s+", " ", str(row.get("title", ""))).strip()
            source = str(row.get("source", "")).strip()
            if title:
                lines.append(f"• {title}" + (f" ({source})" if source else ""))

    lines += [
        "",
        "What to watch next",
        "• Check upcoming central-bank decisions, inflation data, earnings and major global developments.",
        "",
        "Note: Figures are indicative and may be delayed. Verify prices, dates and headline context against the original sources before publishing. This is market information, not investment advice.",
        "",
        "#StockMarket #IndianMarkets #GlobalMarkets #Commodities #MarketUpdate",
    ]
    return "\n".join(lines)
