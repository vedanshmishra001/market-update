# Daily Market Pulse

A free starter project for an automatically refreshed market dashboard and LinkedIn-ready daily market draft.

## Included

- Streamlit dashboard with market snapshot, historical chart, news headlines and post draft.
- Scheduled GitHub Actions workflow.
- Daily saved snapshots in CSV files.
- Google News RSS headlines.
- Python-based daily return calculations.
- No paid AI API required.

## Important data and publishing note

The default price adapter uses `yfinance`, an unofficial retrieval library. It is useful for a personal prototype but it is **not an official exchange feed**. Data availability, delays, adjustments, symbol coverage and terms can change. Do not assume that data displayed by a public website may be redistributed. Before publishing market prices to a public audience or using this commercially, verify the provider's current terms and exchange licensing requirements. Replace `fetch_prices()` in `market_tracker.py` with a data source that explicitly permits your intended display and redistribution.

Google News RSS is used to discover headlines and link back to publisher pages. Headlines are not proof of a story's accuracy; review the original article and context before posting. The generated commentary deliberately does not claim that a particular headline caused a market move.

This project is for information and education, not investment advice.

## Run locally

Requires Python 3.11 or 3.12.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python update_data.py
streamlit run app.py
```

Open the local URL printed by Streamlit.

## Deploy the website for free

1. Create a GitHub account if you do not have one.
2. Create a repository called `daily-market-pulse`.
3. Upload all project files and folders from this project.
4. In the repository, open **Settings → Actions → General** and ensure workflows are allowed.
5. Open **Actions**, select **Daily market data update**, and click **Run workflow** once to test it.
6. Check the workflow log. It should commit `data/snapshots.csv`, `data/news.csv`, and `data/latest_report.md`. If it fails, inspect the log and fix the reported error.
7. Visit [Streamlit Community Cloud](https://share.streamlit.io/), sign in with GitHub, choose **Create app**, select the repository, branch `main`, and file `app.py`.
8. Deploy. The app will get a `streamlit.app` URL.

The Streamlit app and GitHub Actions runner are separate. GitHub Actions performs scheduled updates even while your laptop is off. Streamlit Community Cloud may sleep when unused; the next visitor can wake it up.

## Schedule

The workflow is scheduled for weekdays at 16:30 India Standard Time and 03:00 IST the following morning. GitHub Actions cron runs in UTC. Scheduled runs can be delayed, and US daylight-saving changes mean the second schedule is not always exactly after the US close. Check timestamps in the saved data before publishing.

## How to use

- Click **Refresh data now** to update manually.
- Filter by market group.
- Choose an instrument to inspect its saved history.
- Review the news and click through to original publishers.
- Copy or download the LinkedIn draft, then manually verify figures and context before posting.

## Current limitations

- Historical data only begins when you start saving snapshots.
- The initial adapter uses daily bars, not licensed real-time quotes.
- News headlines are gathered from RSS, not a complete paid newswire.
- Some symbols or data sources can fail temporarily.
- The first version uses rule-based formatting and does not generate verified causal market analysis.
- CSVs committed to Git are fine for a small starter dataset; for long-term use, consider a database or object store with a free tier, while checking its current limits.
