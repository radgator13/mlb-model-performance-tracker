import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# === CONFIG ===
PICKS_FILE = "picks_log.csv"
SEASON_START = datetime(2025, 3, 27)

# === UTILS ===

def color_result(val):
    if val == "WIN":
        return "background-color: lightgreen"
    elif val == "LOSS":
        return "background-color: lightcoral"
    elif val == "PENDING":
        return "background-color: lightyellow"
    return ""

def get_record(series):
    wins = (series == "WIN").sum()
    losses = (series == "LOSS").sum()
    return f"{wins}–{losses}"

def format_percent(p):
    return f"{p:.1f}%" if pd.notnull(p) else "—"

def confidence_score(pick, value):
    try:
        if "Over" in pick or "Under" in pick:
            diff = abs(float(pick.split()[1]) - float(value))
        else:
            diff = abs(float(value))
        if diff >= 3.0:
            return "🔥🔥🔥🔥🔥"
        elif diff >= 2.5:
            return "🔥🔥🔥🔥"
        elif diff >= 2.0:
            return "🔥🔥🔥"
        elif diff >= 1.5:
            return "🔥🔥"
        else:
            return "🔥"
    except:
        return "—"

# === STREAMLIT APP ===

st.set_page_config(layout="wide")
st.title("📊 MLB Model Performance Tracker")

# Load and clean
try:
    df = pd.read_csv(PICKS_FILE)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df = df.sort_values("Date")
except Exception as e:
    st.error(f"Failed to load picks: {e}")
    st.stop()

# Sidebar filters
selected_date = st.date_input("Select date to evaluate:", value=datetime.today().date())
filtered_df = df[df["Date"].dt.date == selected_date].copy()

# Add Confidence columns
if not filtered_df.empty:
    filtered_df["Confidence (Spread)"] = filtered_df.apply(
        lambda row: confidence_score(row["Model Pick (Spread)"], row["Actual Margin"]), axis=1
    )
    filtered_df["Confidence (Total)"] = filtered_df.apply(
        lambda row: confidence_score(row["Model Pick (Total)"], row["Actual Total"]), axis=1
    )

# Header: Score Summary
st.success(f"✅ Results for {selected_date.strftime('%B %d, %Y')}")
col1, col2 = st.columns(2)
col1.metric("Spread Record", get_record(filtered_df["Spread Result"]))
col2.metric("Total Record", get_record(filtered_df["Total Result"]))

# Table
styled_df = filtered_df.style.map(color_result, subset=["Spread Result", "Total Result"])
st.dataframe(styled_df, use_container_width=True)

# Chart Toggle
st.markdown("### 📊 Daily Win % (History)")
range_option = st.radio(
    "Win % Chart Range", ["Last 7 Days", "Last 14 Days", "Full Season"], horizontal=True
)

# Filter for valid result rows (WIN/LOSS only)
valid_chart_df = df[df["Spread Result"].isin(["WIN", "LOSS"]) | df["Total Result"].isin(["WIN", "LOSS"])].copy()

# Win rate logic
def compute_win_rate(day_df):
    date = day_df["Day"].iloc[0]
    s_wins = (day_df["Spread Result"] == "WIN").sum()
    s_total = day_df["Spread Result"].isin(["WIN", "LOSS"]).sum()
    t_wins = (day_df["Total Result"] == "WIN").sum()
    t_total = day_df["Total Result"].isin(["WIN", "LOSS"]).sum()
    return {
        "Date": date,
        "Spread Win %": s_wins / s_total * 100 if s_total else None,
        "Total Win %": t_wins / t_total * 100 if t_total else None,
    }

# Floor to date (strip time) for clean daily grouping
valid_chart_df["Day"] = valid_chart_df["Date"].dt.floor("D")

# Apply chart range filter
if range_option == "Last 7 Days":
    chart_df = valid_chart_df[valid_chart_df["Day"] >= pd.to_datetime(selected_date) - pd.Timedelta(days=6)]
elif range_option == "Last 14 Days":
    chart_df = valid_chart_df[valid_chart_df["Day"] >= pd.to_datetime(selected_date) - pd.Timedelta(days=13)]
else:
    chart_df = valid_chart_df.copy()

# Group by day and compute win %
grouped = chart_df.groupby("Day")
history = pd.DataFrame([compute_win_rate(day) for _, day in grouped])

# Fill NaNs with 0.0% for flatline visualization
history["Spread Win %"] = history["Spread Win %"].fillna(0)
history["Total Win %"] = history["Total Win %"].fillna(0)

# Show daily win % metrics
latest = history.iloc[-1] if not history.empty else {}
col1, col2 = st.columns(2)
col1.metric("Spread Win % (Latest)", format_percent(latest.get("Spread Win %")))
col2.metric("Total Win % (Latest)", format_percent(latest.get("Total Win %")))

# Line chart (fix time-based axis labels!)
if not history.empty:
    chart_data = history.set_index("Date")[["Spread Win %", "Total Win %"]]
    chart_data.index = pd.to_datetime(chart_data.index).date  # <-- Key Fix!
    chart_data.index.name = "Date"
    st.line_chart(chart_data, use_container_width=True)
else:
    st.info("No win rate data to display for selected range.")
