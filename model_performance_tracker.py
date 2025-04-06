import streamlit as st
import pandas as pd
import requests
from datetime import date, timedelta
import altair as alt

st.set_page_config(layout="wide")
st.title("📊 MLB Model Performance Tracker with Auto Logging")

PICKS_FILE = "picks_log.csv"
SEASON_START = date(2025, 3, 27)

@st.cache_data
def load_picks_log():
    try:
        return pd.read_csv(PICKS_FILE, parse_dates=["Date"])
    except FileNotFoundError:
        return pd.DataFrame(columns=[
            "Date", "Matchup", "Model Pick (Spread)", "Model Pick (Total)",
            "Actual Margin", "Spread Result", "Actual Total", "Total Result"
        ])

def fetch_final_score(matchup_date: str, team_name: str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={matchup_date}"
    try:
        res = requests.get(url).json()
        for game in res.get("dates", [])[0].get("games", []):
            if team_name in (game["teams"]["home"]["team"]["name"], game["teams"]["away"]["team"]["name"]):
                if "score" not in game["teams"]["home"] or "score" not in game["teams"]["away"]:
                    return None
                return {
                    "home": game["teams"]["home"]["score"],
                    "away": game["teams"]["away"]["score"],
                    "home_team": game["teams"]["home"]["team"]["name"],
                    "away_team": game["teams"]["away"]["team"]["name"]
                }
    except Exception as e:
        st.warning(f"Score fetch error for {team_name} on {matchup_date}: {e}")
    return None

def evaluate_row(row):
    try:
        home_team = row["Matchup"].split(" @ ")[1]
        score = fetch_final_score(row["Date"].strftime("%Y-%m-%d"), home_team)
    except Exception as e:
        st.warning(f"Row eval failed: {row['Matchup']} | {e}")
        return row

    row["Actual Margin"] = "-"
    row["Spread Result"] = "PENDING"
    row["Actual Total"] = "-"
    row["Total Result"] = "PENDING"

    if score is None:
        return row

    actual_margin = score["home"] - score["away"]
    actual_total = score["home"] + score["away"]

    if "Home" in row["Model Pick (Spread)"]:
        spread_line = float(row["Model Pick (Spread)"].split("-")[-1])
        row["Spread Result"] = "WIN" if actual_margin > spread_line else "LOSS"
    elif "Away" in row["Model Pick (Spread)"]:
        spread_line = float(row["Model Pick (Spread)"].split("+")[-1])
        row["Spread Result"] = "WIN" if actual_margin < -spread_line else "LOSS"

    if "Over" in row["Model Pick (Total)"]:
        line = float(row["Model Pick (Total)"].split()[1])
        row["Total Result"] = "WIN" if actual_total > line else "LOSS"
    elif "Under" in row["Model Pick (Total)"]:
        line = float(row["Model Pick (Total)"].split()[1])
        row["Total Result"] = "WIN" if actual_total < line else "LOSS"

    row["Actual Margin"] = actual_margin
    row["Actual Total"] = actual_total
    return row

def simulate_model_picks(game_date):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={game_date}"
    new_picks = []
    try:
        res = requests.get(url).json()
        for game in res.get("dates", [])[0].get("games", []):
            home = game["teams"]["home"]["team"]["name"]
            away = game["teams"]["away"]["team"]["name"]
            matchup = f"{away} @ {home}"
            margin = round((hash(home) - hash(away)) % 5 - 2, 2)
            total = round(8.0 + ((hash(home + away) % 300) / 100.0 - 1.5), 2)
            spread_pick = f"Home -1.5" if margin > 0 else "Away +1.5"
            total_pick = f"Over {total}" if total > 8 else f"Under {total}"
            new_picks.append({
                "Date": pd.to_datetime(game_date),
                "Matchup": matchup,
                "Model Pick (Spread)": spread_pick,
                "Model Pick (Total)": total_pick
            })
    except Exception as e:
        st.warning(f"Failed to simulate picks for {game_date}: {e}")
    return new_picks

def update_picks_log(selected_date):
    log_df = load_picks_log()
    existing_matchups = set(log_df[log_df["Date"] == pd.to_datetime(selected_date)]["Matchup"])
    new_picks = simulate_model_picks(selected_date)
    new_entries = [p for p in new_picks if p["Matchup"] not in existing_matchups]
    if new_entries:
        new_df = pd.DataFrame(new_entries)
        updated = pd.concat([log_df, new_df], ignore_index=True)
        updated.to_csv(PICKS_FILE, index=False)
        return updated
    else:
        return log_df

def color_result(val):
    colors = {
        "WIN": "lightgreen",
        "LOSS": "#ffb3b3",
        "PENDING": "#ffffcc"
    }
    return f"background-color: {colors.get(val, 'white')}"

# --- Backfill and evaluate
log_df = load_picks_log()
for d in pd.date_range(start=SEASON_START, end=date.today()):
    log_df = update_picks_log(d.date())

log_df["Date"] = pd.to_datetime(log_df["Date"], errors="coerce")
log_df = log_df.dropna(subset=["Date"])
log_df = log_df.apply(evaluate_row, axis=1)
log_df.to_csv(PICKS_FILE, index=False)

# --- Daily detail
selected_day = st.date_input("Select date to evaluate:", date.today() - timedelta(days=1))
filtered_df = log_df[log_df["Date"].dt.date == selected_day]

st.subheader(f"✅ Results for {selected_day.strftime('%B %d, %Y')}")

if "Spread Result" in filtered_df.columns and "Total Result" in filtered_df.columns:
    spread_wins = (filtered_df["Spread Result"] == "WIN").sum()
    spread_losses = (filtered_df["Spread Result"] == "LOSS").sum()
    total_wins = (filtered_df["Total Result"] == "WIN").sum()
    total_losses = (filtered_df["Total Result"] == "LOSS").sum()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Spread Record", f"{spread_wins}–{spread_losses}")
    with col2:
        st.metric("Total Record", f"{total_wins}–{total_losses}")
    styled_df = filtered_df.style.map(color_result, subset=["Spread Result", "Total Result"])
    st.dataframe(styled_df, use_container_width=True)
else:
    st.dataframe(filtered_df, use_container_width=True)

# --- Daily Win % Chart (Last 7 Days)
st.subheader("📊 Daily Win % (Last 7 Days)")

chart_df = log_df.copy()
chart_df["Date"] = chart_df["Date"].dt.date

evaluated_df = chart_df[
    chart_df["Spread Result"].isin(["WIN", "LOSS"]) &
    chart_df["Total Result"].isin(["WIN", "LOSS"])
]

daily = (
    evaluated_df.groupby("Date")
    .agg({
        "Spread Result": lambda x: (x == "WIN").mean() * 100,
        "Total Result": lambda x: (x == "WIN").mean() * 100
    })
    .rename(columns={"Spread Result": "Spread Win %", "Total Result": "Total Win %"})
    .fillna(0)
)

# Ensure last 7 calendar days appear in chart
all_dates = pd.date_range(end=date.today(), periods=7).date
daily = daily.reindex(all_dates, fill_value=0).reset_index()
daily.rename(columns={"index": "Date"}, inplace=True)

if not daily.empty:
    latest = daily.iloc[-1]
    col3, col4 = st.columns(2)
    with col3:
        st.metric("Spread Win % (Latest)", f"{latest['Spread Win %']:.1f}%")
    with col4:
        st.metric("Total Win % (Latest)", f"{latest['Total Win %']:.1f}%")

    chart_data = daily.melt(id_vars="Date", var_name="Metric", value_name="Win %")
    chart = alt.Chart(chart_data).mark_line(point=True).encode(
        x=alt.X("Date:T", title="Date"),
        y=alt.Y("Win %:Q", title="Daily Win %"),
        color="Metric:N"
    ).properties(height=400)

    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Not enough data to chart win rates.")
