import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# === CONFIG ===
API_KEY = "7141524afacb4ab5a9ee8418096bfcd3"
SEASON_START = datetime(2025, 3, 27)
SEASON_END = datetime.today() - timedelta(days=1)
OUTPUT_FILE = "picks_log.csv"
REQUEST_DELAY = 0.25

# === API CALLS ===

def fetch_odds_by_date(game_date):
    url = f"https://api.sportsdata.io/v3/mlb/odds/json/GameOddsByDate/{game_date.strftime('%Y-%m-%d')}?key={API_KEY}"
    try:
        r = requests.get(url)
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ Odds fetch failed: {e}")
        return []

def fetch_scores_by_date(game_date):
    url = f"https://api.sportsdata.io/v3/mlb/scores/json/GamesByDate/{game_date.strftime('%Y-%m-%d')}?key={API_KEY}"
    try:
        r = requests.get(url)
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ Scores fetch failed: {e}")
        return []

# === EVALUATION ===

def get_pregame_odds(game):
    odds_list = game.get("PregameOdds", [])
    if not odds_list:
        return None, None
    latest = sorted(odds_list, key=lambda x: x.get("Updated", ""))[-1]
    return latest.get("HomePointSpread"), latest.get("OverUnder")

def get_game_score(game_id, scores_data):
    for g in scores_data:
        if g.get("GameID") == game_id:
            return g.get("HomeTeamRuns"), g.get("AwayTeamRuns")
    return None, None

def simulate_model(home, away):
    model_margin = len(home) - len(away)
    model_total = 8.5 + (len(home) % 3)
    return model_margin, model_total

def evaluate_spread(model_margin, vegas_spread, actual_margin):
    model_pick = "Home -1.5" if model_margin > vegas_spread else "Away +1.5"
    result = (
        "WIN" if (model_pick == "Home -1.5" and actual_margin > 1.5) or
                (model_pick == "Away +1.5" and actual_margin < -1.5)
        else "LOSS"
    )
    return model_pick, result

def evaluate_total(model_total, vegas_total, actual_total):
    model_pick = "Over " + str(vegas_total) if model_total > vegas_total else "Under " + str(vegas_total)
    result = (
        "WIN" if (model_pick.startswith("Over") and actual_total > vegas_total) or
                (model_pick.startswith("Under") and actual_total < vegas_total)
        else "LOSS"
    )
    return model_pick, result

# === MAIN SCRIPT ===

def run():
    rows = []
    current = SEASON_START

    while current <= SEASON_END:
        print(f"\n🔄 {current.strftime('%Y-%m-%d')}")
        odds_data = fetch_odds_by_date(current)
        scores_data = fetch_scores_by_date(current)

        for game in odds_data:
            home = game.get("HomeTeamName")
            away = game.get("AwayTeamName")
            game_id = game.get("GameId")

            if not all([home, away, game_id]):
                print("⏩ Skipping game with missing team names or ID.")
                continue

            spread, total = get_pregame_odds(game)

            if None in (spread, total):
                print(f"⏩ {away} @ {home} — missing odds.")
                continue

            home_score, away_score = get_game_score(game_id, scores_data)
            if home_score is None or away_score is None:
                print(f"⏩ {away} @ {home} — missing scores.")
                continue

            actual_margin = home_score - away_score
            actual_total = home_score + away_score

            model_margin, model_total = simulate_model(home, away)
            spread_pick, spread_result = evaluate_spread(model_margin, spread, actual_margin)
            total_pick, total_result = evaluate_total(model_total, total, actual_total)

            rows.append({
                "Date": current.date(),
                "Away Team": away,
                "Home Team": home,
                "Model Pick (Spread)": spread_pick,
                "Model Pick (Total)": total_pick,
                "Actual Margin": actual_margin,
                "Spread Result": spread_result,
                "Actual Total": actual_total,
                "Total Result": total_result
            })

            time.sleep(REQUEST_DELAY)

        current += timedelta(days=1)

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Done! {len(df)} rows written to {OUTPUT_FILE}")

if __name__ == "__main__":
    run()
