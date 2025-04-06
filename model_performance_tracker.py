import streamlit as st
import pandas as pd
import requests
from datetime import date, timedelta

st.set_page_config(layout="wide")
st.title("📊 MLB Model Performance Tracker with Auto Logging")

PICKS_FILE = "picks_log.csv"

# --- Load CSV ---
@st.cache_data
def load_picks_log():
    try:
        return pd.read_csv(PICKS_FILE, parse_dates=["Date"])
    except FileNotFoundError:
        return pd.DataFrame(columns=[
            "Date", "Matchup", "Model Pick (Spread)", "Model Pick (Total)",
            "Actual Margin", "Spread Result", "Actual Total", "Total Result"
        ])

# --- Fetch Game Scores ---
def fetch_final_score(matchup_date: str, team_name: str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={matchup_date}"
    res = requests.get(url).json()

    for game in res.get("dates", [])[0].get("games", []):
        if team_name in (game["teams"]["home"]["team"]["name"], game["teams"]["away"]["team"]["name"]):
            # ✅ Only proceed if scores are available
            if "score" not in game["teams"]["home"] or "score" not in game["teams"]["away"]:
                return None

            return {
                "home": game["teams"]["home"]["score"],
                "away": game["teams"]["away"]["score"],
                "home_team": game["teams"]["home"]["team"]["name"],
                "away_team": game["teams"]["away"]["team"]["name"]
            }

    return None


# --- Evaluate Row ---
def evaluate_row(row):
    score = fetch_final_score(row["Date"].strftime("%Y-%m-%d"), row["Matchup"].split(" @ ")[1])
    if score is None:
        return row

    actual_margin = score["home"] - score["away"]
    actual_total = score["home"] + score["away"]

    # Evaluate Spread
    spread_result = "PUSH"
    if "Home" in row["Model Pick (Spread)"]:
        spread_line = float(row["Model Pick (Spread)"].split("-")[-1])
        spread_result = "WIN" if actual_margin > spread_line else "LOSS"
    elif "Away" in row["Model Pick (Spread)"]:
        spread_line = float(row["Model Pick (Spread)"].split("+")[-1])
        spread_result = "WIN" if actual_margin < -spread_line else "LOSS"

    # Evaluate Total
    total_result = "PUSH"
    if "Over" in row["Model Pick (Total)"]:
        line = float(row["Model Pick (Total)"].split()[1])
        total_result = "WIN" if actual_total > line else "LOSS"
    elif "Under" in row["Model Pick (Total)"]:
        line = float(row["Model Pick (Total)"].split()[1])
        total_result = "WIN" if actual_total < line else "LOSS"

    row["Actual Margin"] = actual_margin
    row["Spread Result"] = spread_result
    row["Actual Total"] = actual_total
    row["Total Result"] = total_result
    return row

# --- Auto-generate Model Picks (placeholder logic) ---
def simulate_model_picks(game_date):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={game_date}"
    res = requests.get(url).json()
    new_picks = []

    if not res.get("dates"):
        return []

    for game in res["dates"][0].get("games", []):
        home = game["teams"]["home"]["team"]["name"]
        away = game["teams"]["away"]["team"]["name"]
        matchup = f"{away} @ {home}"

        # Example placeholder model logic:
        margin = round((hash(home) - hash(away)) % 5 - 2, 2)  # fake margin
        total = round(8.0 + ((hash(home + away) % 300) / 100.0 - 1.5), 2)  # fake total

        spread_pick = f"Home -1.5" if margin > 0 else "Away +1.5"
        total_pick = f"Over {total}" if total > 8 else f"Under {total}"

        new_picks.append({
            "Date": pd.to_datetime(game_date),
            "Matchup": matchup,
            "Model Pick (Spread)": spread_pick,
            "Model Pick (Total)": total_pick
        })

    return new_picks

# --- Auto-log New Picks ---
def update_picks_log(selected_date):
    log_df = load_picks_log()
    existing_matchups = set(log_df[log_df["Date"] == pd.to_datetime(selected_date)]["Matchup"])

    new_picks = simulate_model_picks(selected_date)
    new_entries = [p for p in new_picks if p["Matchup"] not in existing_matchups]

    if new_entries:
        st.success(f"📥 Added {len(new_entries)} new picks for {selected_date}")
        new_df = pd.DataFrame(new_entries)
        updated = pd.concat([log_df, new_df], ignore_index=True)
        updated.to_csv(PICKS_FILE, index=False)
        return updated
    else:
        st.info("No new picks to add for this date.")
        return log_df

# --- Main Logic ---
selected_day = st.date_input("Select date to evaluate:", date.today() - timedelta(days=1))
log_df = update_picks_log(selected_day)

if not log_df.empty:
    log_df["Date"] = pd.to_datetime(log_df["Date"], errors="coerce")
    log_df = log_df.dropna(subset=["Date"])

    filtered_df = log_df[log_df["Date"].dt.date == selected_day]
    evaluated = filtered_df.apply(evaluate_row, axis=1)

    # --- Record Summary ---
    st.subheader(f"✅ Results for {selected_day.strftime('%B %d, %Y')}")
    spread_wins = (evaluated["Spread Result"] == "WIN").sum()
    spread_losses = (evaluated["Spread Result"] == "LOSS").sum()
    total_wins = (evaluated["Total Result"] == "WIN").sum()
    total_losses = (evaluated["Total Result"] == "LOSS").sum()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Spread Record", f"{spread_wins}–{spread_losses}")
    with col2:
        st.metric("Total Record", f"{total_wins}–{total_losses}")

    st.dataframe(evaluated.reset_index(drop=True), use_container_width=True)

    # --- Save back to log ---
    final_log = pd.concat([log_df[log_df["Date"].dt.date != selected_day], evaluated])
    final_log.to_csv(PICKS_FILE, index=False)
else:
    st.warning("No games or picks found for this date.")
