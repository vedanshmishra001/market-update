import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from market_tracker import (
    DATA_DIR, SNAPSHOT_FILE, NEWS_FILE, REPORT_FILE,
    run_update, load_snapshots, load_news, build_linkedin_post
)

st.set_page_config(page_title="Daily Market Pulse", page_icon="📈", layout="wide")
st.title("📈 Daily Market Pulse")
st.caption("India • US • Commodities • FX • Macro • News")
st.info(
    "Research prototype. Quotes may be delayed, incomplete, or unavailable on holidays. "
    "Verify important figures against official sources before publishing. Do not treat this as investment advice."
)

with st.sidebar:
    st.subheader("Controls")
    st.write("Data refresh is scheduled by GitHub Actions. You can also refresh manually.")
    if st.button("Refresh data now", type="primary", use_container_width=True):
        with st.spinner("Fetching latest available data..."):
            messages = run_update()
        for message in messages:
            st.write("• " + message)
        st.rerun()
    st.caption("Last refresh is shown below when available.")
    st.divider()
    st.write("**Data coverage**")
    st.write("• Market prices: Yahoo Finance via yfinance (prototype adapter)")
    st.write("• Headlines: Google News RSS")
    st.write("• US macro: FRED CSV endpoints where available")

snapshots = load_snapshots()
news = load_news()

if snapshots.empty:
    st.warning("No snapshots yet. Click **Refresh data now**, or wait for the first scheduled GitHub Actions run.")
else:
    snapshots["date"] = pd.to_datetime(snapshots["date"], errors="coerce")
    latest_date = snapshots["date"].max()
    latest = snapshots[snapshots["date"] == latest_date].copy()
    latest = latest.sort_values(["group", "name"])

    st.caption(f"Latest saved snapshot: {latest_date.strftime('%d %b %Y')}")
    index_groups = latest[latest["group"].isin(["India indices", "US indices"])]
    if not index_groups.empty:
        cols = st.columns(min(4, len(index_groups)))
        for col, (_, row) in zip(cols, index_groups.iterrows()):
            pct = row.get("change_pct")
            delta = f"{pct:+.2f}%" if pd.notna(pct) else None
            col.metric(str(row["name"]), f'{row["close"]:,.2f}' if pd.notna(row["close"]) else "N/A", delta)

    st.subheader("Latest market snapshot")
    group_filter = st.multiselect(
        "Filter market group",
        options=sorted(latest["group"].dropna().unique().tolist()),
        default=sorted(latest["group"].dropna().unique().tolist())
    )
    view = latest[latest["group"].isin(group_filter)].copy()
    display_cols = ["group", "name", "symbol", "close", "change_pct", "date", "source"]
    view = view[[c for c in display_cols if c in view.columns]]
    if "change_pct" in view:
        view["change_pct"] = view["change_pct"].map(lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A")
    st.dataframe(view, use_container_width=True, hide_index=True)

    st.subheader("Historical performance")
    names = sorted(snapshots["name"].dropna().unique().tolist())
    selected = st.selectbox("Choose an instrument", names)
    history = snapshots[snapshots["name"] == selected].sort_values("date")
    if not history.empty:
        fig = px.line(history, x="date", y="close", title=f"{selected} — saved closing prices")
        fig.update_layout(xaxis_title="", yaxis_title="Close", margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Market news")
if news.empty:
    st.write("No headlines saved yet. Refresh data or check the scheduled workflow.")
else:
    for _, row in news.head(25).iterrows():
        title = str(row.get("title", "Untitled"))
        source = str(row.get("source", "Source not provided"))
        published = str(row.get("published", ""))
        url = str(row.get("url", ""))
        st.markdown(f"**[{title}]({url})**")
        st.caption(f"{source} • {published}")

st.divider()
st.subheader("LinkedIn-ready daily market post")
if REPORT_FILE.exists():
    post = build_linkedin_post(snapshots, news)
    st.text_area("Review and copy this draft before posting", value=post, height=360)
    st.download_button("Download post as .txt", data=post, file_name="daily_market_post.txt", mime="text/plain")
else:
    st.write("A draft will appear after the first successful refresh.")

st.caption("Built with Python + Streamlit. No paid AI service is required.")
