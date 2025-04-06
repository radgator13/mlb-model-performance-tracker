import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import plotly.express as px
import os

PICKS_FILE = "picks_log.csv"
SEASON_START = date(2025, 3, 27)

st.set_page_config(layout="wide")

st.title("📊 MLB Model Performance Tracker")

# Load and evaluate picks_log.csv
@st.cache_data
def load_picks_log():
    if os.path.exists(PICKS_FILE):
        df = pd.read_csv(PICKS_FILE)
        return df
    else:
        return pd.DataFrame()

def parse_float(val):
    try:
        return float(str(val).strip())
    except:
        return None

def reevaluate(row):
    try:
        if row["Spread Result"] not in ["WIN", "LOSS"] or row["Total Result"] not in ["WIN", "LOSS"]:
            margin = parse_float(row["Actual Margin"])
            total = parse_float(row["Actual Total"])
            spread_val = parse_float(row["Model Pick (Spread)"].split()[-1])
            total_val = parse_float(row["Model Pick (Total)"].split()[-1])

            if margin is not None:
                if "Home" in row["Model Pick (Spread)"] and margin > 1.5:
                    row["Spread Result"] = "WIN"
                elif "Away" in row["Model Pick (Spread)"] and margin < -1.5:
                    row["Spread Result"] = "WIN"
                else:
                    row["Spread Result"] = "LOSS"

            if total is not None and total_val is not None:
                if "Over" in row["Model Pick (Total)"] and total > total_val:
                    row["Total Result"] = "WIN"
                elif "Under" in row["Model Pick (Total)"] and total < total_val:
                    row["Total Result"] = "WIN"
                else:
                    row["Total Result"] = "LOSS"
    except:
        row["Spread Result"] = "PENDING"
        row["Total Result"] = "PENDING"

    return row

df = load_picks_log()
if not df.empty:
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df = df.apply(reevaluate, axis=1)

    # Save updated file
    df.to_csv(PICKS_FILE, index=False)

    # Sidebar
    st.markdown("### Select date to evaluate:")
    selected_date = st.date_input("Date", value=date.today())

    filtered_df = df[df["Date"].dt.date == selected_date]

    st.success(f"✅ Results for {selected_date.strftime('%B %d, %Y')}")

    spread_wins = (filtered_df["Spread Result"] == "WIN").sum()
    spread_total = (filtered_df["Spread Result"].isin(["WIN", "LOSS"])).sum()
    total_wins = (filtered_df["Total Result"] == "WIN").sum()
    total_total = (filtered_df["Total Result"].isin(["WIN", "LOSS"])).sum()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Spread Record**")
        st.metric(label="", value=f"{spread_wins}–{spread_total - spread_wins}")
    with col2:
        st.markdown("**Total Record**")
        st.metric(label="", value=f"{total_wins}–{total_total - total_wins}")

    # Highlight pending games
    def color_result(val):
        if val == "WIN":
            return "background-color: #c8f7c5"
        elif val == "LOSS":
            return "background-color: #f4bbbb"
        elif val == "PENDING":
            return "background-color: #fef8cd"
        return ""

    styled_df = filtered_df.style.applymap(color_result, subset=["Spread Result", "Total Result"])
    st.dataframe(styled_df, use_container_width=True)

    # === Rolling Chart ===
    st.markdown("### 📈 Daily Win % (History)")

    win_range = st.radio("Win % Chart Range", ["Last 7 Days", "Last 14 Days", "Full Season"], horizontal=True)

    if win_range == "Last 7 Days":
        days_back = 7
    elif win_range == "Last 14 Days":
        days_back = 14
    else:
        days_back = (date.today() - SEASON_START).days + 1

    recent = df.copy()
    recent["Date"] = pd.to_datetime(recent["Date"], errors="coerce")
    recent = recent.dropna(subset=["Date"])
    recent = recent[recent["Date"].dt.date >= (date.today() - timedelta(days=days_back))]

    daily_stats = (
        recent[recent["Spread Result"].isin(["WIN", "LOSS"])]
        .groupby(recent["Date"].dt.date)
        .agg(
            Spread_Win_Pct=("Spread Result", lambda x: (x == "WIN").sum() / len(x) * 100),
        )
        .reset_index()
        .rename(columns={"Date": "Game Date"})
    )

    total_stats = (
        recent[recent["Total Result"].isin(["WIN", "LOSS"])]
        .groupby(recent["Date"].dt.date)
        .agg(
            Total_Win_Pct=("Total Result", lambda x: (x == "WIN").sum() / len(x) * 100),
        )
        .reset_index()
        .rename(columns={"Date": "Game Date"})
    )

    chart_df = pd.merge(daily_stats, total_stats, on="Game Date", how="outer").fillna(0)
    chart_df = chart_df.sort_values(by="Game Date")

    latest_spread = chart_df["Spread_Win_Pct"].iloc[-1] if not chart_df.empty else 0
    latest_total = chart_df["Total_Win_Pct"].iloc[-1] if not chart_df.empty else 0

    col1, col2 = st.columns(2)
    col1.metric("Spread Win % (Latest)", f"{latest_spread:.1f}%")
    col2.metric("Total Win % (Latest)", f"{latest_total:.1f}%")

    fig = px.line(
        chart_df,
        x="Game Date",
        y=["Spread_Win_Pct", "Total_Win_Pct"],
        labels={"value": "Daily Win %", "variable": "Metric"},
        title="",
        markers=True
    )
    fig.update_layout(legend_title="Metric", height=400)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("picks_log.csv not found or empty.")
