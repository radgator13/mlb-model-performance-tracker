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

def confidence_level(diff):
    if pd.isna(diff):
        return ""
    if diff >= 3.0:
        return "🔥🔥🔥🔥🔥"
    elif diff >= 2.0:
        return "🔥🔥🔥🔥"
    elif diff >= 1.5:
        return "🔥🔥🔥"
    elif diff >= 1.0:
        return "🔥🔥"
    elif diff >= 0.5:
        return "🔥"
    return ""

# === STREAMLIT APP ===

st.set_page_config(layout="wide")
st.title("📊 MLB Model Performance Tracker")

# Load and clean
try:
    df = pd.read_csv(PICKS_FILE)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df = df.sort_values("Date")

    # === Add confidence levels ===
    df["Vegas Spread"] = df["Model Pick (Spread)"].apply(lambda x: -1.5 if "Home" in str(x) else 1.5)
    df["Vegas Total"] = df["Model Pick (Total)"].str.extract(r"(\d+\.\d+)").astype(float)

    # Simulated model values — replace with real model output if available
    df["Model Margin"] = df["Vegas Spread"]
    df["Model Total"] = df["Vegas Total"]

    df["Confidence (Spread)"] = abs(df["Model Margin"] - df["Vegas Spread"]).apply(confidence_level)
    df["Confidence (Total)"] = abs(df["Model Total"] - df["Vegas Total"]).apply(confidence_level)

except Exception as e:
    st.error(f"Failed to load picks: {e}")
    st.stop()

# Sidebar filters
selected_date = st.date_input("Select date to evaluate:", value=datetime.today().date())
filtered_df = df[df["Date"].dt.date == selected_date]

# Header: Score Summary
st.success(f"✅ Results for {selected_date.strftime('%B %d, %Y')}")
col1, col2 = st.columns(2)

col1.metric("Spread Record", get_record(filtered_df["Spread Result"]))
col2.metric("Total Record", get_record(filtered_df["Total Result"]))

# Table Display
cols_to_show = [
    "Date", "Away Team", "Home Team",
    "Model Pick (Spread)", "Confidence (Spread)", "Spread Result",
    "Model Pick (Total)", "Confidence (Total)", "Total Result",
    "Actual Margin", "Actual Total"
]

styled_df = filtered_df[cols_to_show].style.map(color_result, subset=["Spread Result", "Total Result"])
st.dataframe(styled_df, use_container_width=True)

# Chart Toggle
st.markdown("### 📊 Daily Win % (History)")
range_option = st.radio(
    "Win % Chart Range", ["Last 7 Days", "Last 14 Days", "Full Season"], horizontal=True
)

# Win rate logic
def compute_win_rate(day_df):
    date = day_df["Date"].iloc[0].date()
    s = get_record(day_df["Spread Result"])
    t = get_record(day_df["Total Result"])
    s_wins = (day_df["Spread Result"] == "WIN").sum()
    s_total = day_df["Spread Result"].isin(["WIN", "LOSS"]).sum()
    t_wins = (day_df["Total Result"] == "WIN").sum()
    t_total = day_df["Total Result"].isin(["WIN", "LOSS"]).sum()
    return {
        "Date": date,
        "Spread Win %": s_wins / s_total * 100 if s_total else None,
        "Total Win %": t_wins / t_total * 100 if t_total else None,
    }

if range_option == "Last 7 Days":
    chart_df = df[df["Date"] >= pd.to_datetime(selected_date) - pd.Timedelta(days=6)]
elif range_option == "Last 14 Days":
    chart_df = df[df["Date"] >= pd.to_datetime(selected_date) - pd.Timedelta(days=13)]
else:
    chart_df = df.copy()

grouped = chart_df.groupby(chart_df["Date"].dt.date)
history = pd.DataFrame([compute_win_rate(day) for _, day in grouped])

# Show daily win % metrics
latest = history.iloc[-1] if not history.empty else {}
col1, col2 = st.columns(2)
col1.metric("Spread Win % (Latest)", format_percent(latest.get("Spread Win %")))
col2.metric("Total Win % (Latest)", format_percent(latest.get("Total Win %")))

# Line chart
if not history.empty:
    chart_data = history.set_index("Date")[["Spread Win %", "Total Win %"]]
    st.line_chart(chart_data, use_container_width=True)
else:
    st.info("No win rate data to display for selected range.")
