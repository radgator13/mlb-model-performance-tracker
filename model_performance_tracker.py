﻿import streamlit as st
import pandas as pd
import requests
from datetime import date, datetime

st.set_page_config(layout="wide")
st.title("📊 MLB Model Performance Tracker")

# --- Load Prediction Log ---
@st.cache_data
def load_picks_log():
    try:
        return pd.read_csv("picks_log.csv", parse_dates=["Date"])
    except FileNotFoundError:
        return pd.DataFrame(columns=[
            "Date", "Matchup", "Model Pick (Spread)", "Model Pick (Total)"
        ])

picks_df = load_picks_log()

# --- MLB API Final Scores ---
def fetch_final_score(matchup_date: str, team_name: str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={matchup_date}"
    res = requests.get(url).json()
    for game in res.get("dates", [])[0].get("games", []):
        if team_name in (game["teams"]["home"]["team"]["name"], game["teams"]["away"]["team"]["name"]):
            return {
                "home": game["teams"]["home"]["score"],
                "away": game["teams"]["away"]["score"],
                "home_team": game["teams"]["home"]["team"]["name"],
                "away_team": game["teams"]["away"]["team"]["name"]
            }
    return None

# --- Evaluate Each Row ---
def evaluate_row(row):
    try:
        score = fetch_final_score(row["Date"].strftime("%Y-%m-%d"), row["Matchup"].split(" @ ")[1])
        if score is None:
            return row

        actual_margin = score["home"] - score["away"]
        actual_total = score["home"] + score["away"]

        # Evaluate spread
        spread_result = "PUSH"
        if "Home" in row["Model Pick (Spread)"]:
            spread_line = float(row["Model Pick (Spread)"].split("-")[-1])
            spread_result = "WIN" if actual_margin > spread_line else "LOSS"
        elif "Away" in row["Model Pick (Spread)"]:
            spread_line = float(row["Model Pick (Spread)"].split("+")[-1])
            spread_result = "WIN" if actual_margin < -spread_line else "LOSS"

        # Evaluate total
        total_result = "PUSH"
        if "Over" in row["Model Pick (Total)"]:
            line = float(row["Model Pick (Total)"].split()[1])
            total_result = "WIN" if actual_total > line else "LOSS"
        elif "Under" in row["Model Pick (Total)"]:
            line = float(row["Model Pick (Total)"].split()[1])
            total_result = "WIN" if actual_total < line else "LOSS"

        row["Actual Margin"] = actual_margin
        row["Actual Total"] = actual_total
        row["Spread Result"] = spread_result
        row["Total Result"] = total_result
    except:
        pass
    return row

# --- Evaluate & Update Picks ---
if not picks_df.empty:
    st.info("📦 Evaluating model picks...")

    picks_df["Date"] = pd.to_datetime(picks_df["Date"], errors="coerce")
    picks_df = picks_df.dropna(subset=["Date"])

    evaluated = picks_df.apply(evaluate_row, axis=1)
    evaluated.to_csv("picks_log.csv", index=False)
    st.success("✅ Picks evaluated and updated!")

    # --- Overall Performance ---
    spread_record = evaluated["Spread Result"].value_counts()
    total_record = evaluated["Total Result"].value_counts()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Spread Record", f"{spread_record.get('WIN',0)}–{spread_record.get('LOSS',0)}")
        st.metric("Spread Win %", f"{(spread_record.get('WIN',0) / max(1,spread_record.sum()) * 100):.1f}%")
    with col2:
        st.metric("Total Record", f"{total_record.get('WIN',0)}–{total_record.get('LOSS',0)}")
        st.metric("Total Win %", f"{(total_record.get('WIN',0) / max(1,total_record.sum()) * 100):.1f}%")

    # --- Date Picker Filter ---
    st.subheader("📅 View Model Performance by Date")

    available_dates = evaluated["Date"].dt.date.unique()
    selected_date = st.date_input("Select a date to review:", value=available_dates[-1], min_value=min(available_dates), max_value=max(available_dates))

    selected_day_df = evaluated[evaluated["Date"].dt.date == selected_date]

    if not selected_day_df.empty:
        spread_wins = (selected_day_df["Spread Result"] == "WIN").sum()
        spread_losses = (selected_day_df["Spread Result"] == "LOSS").sum()
        total_wins = (selected_day_df["Total Result"] == "WIN").sum()
        total_losses = (selected_day_df["Total Result"] == "LOSS").sum()

        col3, col4 = st.columns(2)
        with col3:
            st.metric("Spread Record", f"{spread_wins}–{spread_losses}")
        with col4:
            st.metric("Total Record", f"{total_wins}–{total_losses}")

        st.markdown("### 📋 Picks for Selected Date")
        st.dataframe(selected_day_df.reset_index(drop=True), use_container_width=True)
    else:
        st.info("No picks found for that date.")

    # --- Full Log ---
    st.subheader("📋 Full Evaluated Picks Log")
    st.dataframe(evaluated.reset_index(drop=True), use_container_width=True)
else:
    st.warning("No picks found yet. Add entries to `picks_log.csv`.")
