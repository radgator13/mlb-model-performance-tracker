import streamlit as st
import pandas as pd
import requests
import os
from datetime import date, timedelta
import altair as alt

st.set_page_config(layout="wide")
st.title("📊 MLB Model Performance Tracker")

PICKS_FILE = "picks_log.csv"
SEASON_START = date(2025, 3, 27)

# --- Ensure picks_log.csv exists with correct structure
def initialize_log_file():
    if not os.path.exists(PICKS_FILE):
        columns = [
            "Date", "Away Team", "Home Team",
            "Model Pick (Spread)", "Model Pick (Total)",
            "Actual Margin", "Spread Result", "Actual Total", "Total Result"
        ]
        pd.DataFrame(columns=columns).to_csv(PICKS_FILE, index=False)

@st.cache_data
def load_picks_log():
    initialize_log_file()
    return pd.read_csv(PICKS_FILE, parse_dates=["Date"])

def fetch_final_score(game_date: str, home_team: str, away_team: str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={game_date}"
    try:
        res = requests.get(url).json()
        for game in res.get("dates", [])[0].get("games", []):
            ht = game["teams"]["home"]["team"]["name"]
            at = game["teams"]["away"]["team"]["name"]
            if ht == home_team and at == away_team:
                if "score" not in game["teams"]["home"] or "score" not in game["teams"]["away"]:
                    return None
                return {
                    "home_score": game["teams"]["home"]["score"],
                    "away_score": game["teams"]["away"]["score"]
                }
    except Exception as e:
        st.warning(f"Score fetch error for {home_team} vs {away_team}: {e}")
    return None

def evaluate_row(row):
    score = fetch_final_score(row["Date"].strftime("%Y-%m-%d"), row["Home Team"], row["Away Team"])
    row["Actual Margin"] = "-"
    row["Actual Total"] = "-"
    row["Spread Result"] = "PENDING"
    row["Total Result"] = "PENDING"
    if not score:
        return row

    margin = score["home_score"] - score["away_score"]
    total = score["home_score"] + score["away_score"]
    row["Actual Margin"] = margin
    row["Actual Total"] = total

    if "Home" in row["Model Pick (Spread)"]:
        line = float(row["Model Pick (Spread)"].split("-")[-1])
        row["Spread Result"] = "WIN" if margin > line else "LOSS"
    else:
        line = float(row["Model Pick (Spread)"].split("+")[-1])
        row["Spread Result"] = "WIN" if margin < -line else "LOSS"

    if "Over" in row["Model Pick (Total)"]:
        line = float(row["Model Pick (Total)"].split()[-1])
        row["Total Result"] = "WIN" if total > line else "LOSS"
    else:
        line = float(row["Model Pick (Total)"].split()[-1])
        row["Total Result"] = "WIN" if total < line else "LOSS"

    return row

def simulate_model_picks(game_date):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={game_date}"
    picks = []
    try:
        res = requests.get(url).json()
        for game in res.get("dates", [])[0].get("games", []):
            home = game["teams"]["home"]["team"]["name"]
            away = game["teams"]["away"]["team"]["name"]

            spread_pick = "Home -1.5" if len(home) > len(away) else "Away +1.5"
            total_pick = "Over 8.5" if "a" in home.lower() else "Under 8.5"

            picks.append({
                "Date": pd.to_datetime(game_date),
                "Away Team": away,
                "Home Team": home,
                "Model Pick (Spread)": spread_pick,
                "Model Pick (Total)": total_pick
            })
    except Exception as e:
        st.warning(f"Could not simulate picks for {game_date}: {e}")
    return picks

def update_picks_log(game_date):
    log_df = load_picks_log()
    existing = set(
        tuple(row) for row in log_df[["Date", "Away Team", "Home Team"]].values
    )
    new_picks = simulate_model_picks(game_date)
    filtered = [
        p for p in new_picks if (p["Date"], p["Away Team"], p["Home Team"]) not in existing
    ]
    if filtered:
        new_df = pd.DataFrame(filtered)
        log_df = pd.concat([log_df, new_df], ignore_index=True)
        log_df.to_csv(PICKS_FILE, index=False)
    return log_df

def color_result(val):
    colors = {
        "WIN": "lightgreen",
        "LOSS": "#ffb3b3",
        "PENDING": "#ffffcc"
    }
    return f"background-color: {colors.get(val, 'white')}"

# --- Backfill and evaluate full log
log_df = load_picks_log()
for d in pd.date_range(SEASON_START, date.today()):
    log_df = update_picks_log(d.date())

log_df["Date"] = pd.to_datetime(log_df["Date"], errors="coerce")
log_df = log_df.dropna(subset=["Date"])
log_df = log_df.apply(evaluate_row, axis=1)
log_df.to_csv(PICKS_FILE, index=False)

# --- Daily evaluation
selected_day = st.date_input("Select date to evaluate:", date.today() - timedelta(days=1))
daily_df = log_df[log_df["Date"].dt.date == selected_day]

st.subheader(f"✅ Results for {selected_day.strftime('%B %d, %Y')}")

if not daily_df.empty:
    spread_wins = (daily_df["Spread Result"] == "WIN").sum()
    spread_losses = (daily_df["Spread Result"] == "LOSS").sum()
    total_wins = (daily_df["Total Result"] == "WIN").sum()
    total_losses = (daily_df["Total Result"] == "LOSS").sum()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Spread Record", f"{spread_wins}–{spread_losses}")
    with col2:
        st.metric("Total Record", f"{total_wins}–{total_losses}")

    styled = daily_df.style.map(color_result, subset=["Spread Result", "Total Result"])
    st.dataframe(styled, use_container_width=True)
else:
    st.info("No picks found for selected date.")

# --- Win % Chart (7 Days)
st.subheader("📊 Daily Win % (Last 7 Days)")

chart_df = log_df.copy()
chart_df["Date"] = chart_df["Date"].dt.date

eval_df = chart_df[
    chart_df["Spread Result"].isin(["WIN", "LOSS"]) &
    chart_df["Total Result"].isin(["WIN", "LOSS"])
]

grouped = (
    eval_df.groupby("Date")
    .agg({
        "Spread Result": lambda x: (x == "WIN").mean() * 100,
        "Total Result": lambda x: (x == "WIN").mean() * 100
    })
    .rename(columns={"Spread Result": "Spread Win %", "Total Result": "Total Win %"})
)
# WIN % CHART TOGGLE ADDED
# Force last 7 calendar days
dates = pd.date_range(end=date.today(), periods=7).date
grouped = grouped.reindex(dates, fill_value=0).reset_index().rename(columns={"index": "Date"})

if not grouped.empty:
    latest = grouped.iloc[-1]
    col3, col4 = st.columns(2)
    with col3:
        st.metric("Spread Win % (Latest)", f"{latest['Spread Win %']:.1f}%")
    with col4:
        st.metric("Total Win % (Latest)", f"{latest['Total Win %']:.1f}%")

    melt = grouped.melt(id_vars="Date", var_name="Metric", value_name="Win %")
    chart = alt.Chart(melt).mark_line(point=True).encode(
        x="Date:T",
        y="Win %:Q",
        color="Metric:N"
    ).properties(height=400)

    st.altair_chart(chart, use_container_width=True)
else:
    st.info("No win rate data available.")
