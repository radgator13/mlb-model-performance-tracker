import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# === CONFIG ===
API_KEY = "7141524afacb4ab5a9ee8418096bfcd3"
SEASON_START = datetime(2025, 3, 27)
SEASON_END = datetime.today() - timedelta(days=1)
OUTPUT_FILE = "picks_log.csv"
REQUEST_DELAY = 0.5


# === API ===

def fetch_odds_by_date(game_date):
    url = f"https://api.sportsdata.io/v3/mlb/odds/json/GameOddsByDate/{game_date.strftime('%Y-%m-%d')}?key={API_KEY}"
    try:
        r = requests.get(url)
        return r.json() if isinstance(r.json(), list) else []
    except:
        return []


def fetch_scores_by_date(game_date):
    url = f"https://api.sportsdata.io/v3/mlb/scores/json/GamesByDate/{game_date.strftime('%Y-%m-%d')}?key={API_KEY}"
    try:
        r = requests.get(url)
        return r.json() if isinstance(r.json(), list) else []
    except:
        return []


# === MODEL ===

def simulate_model(home, away):
    model_margin = len(home) - len(away)
    model_total = 8.5 + ((len(home) + len(away)) % 3)
    return model_margin, model_total


def evaluate_spread(model_margin, vegas_spread, actual_margin):
    model_pick = "Home -1.5" if model_margin > vegas_spread else "Away +1.5"
    result = (
        "WIN" if (model_pick == "Home -1.5" and actual_margin > 1.5)
        or (model_pick == "Away +1.5" and actual_margin < -1.5)
        else "LOSS"
    )
    return model_pick, result


def evaluate_total(model_total, vegas_total, actual_total):
    model_pick = f"Over {vegas_total}" if model_total > vegas_total else f"Under {vegas_total}"
    result = (
        "WIN" if (model_pick.startswith("Over") and actual_total > vegas_total)
        or (model_pick.startswith("Under") and actual_total < vegas_total)
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
            away = game.get("AwayTeamName")
            home = game.get("HomeTeamName")
            game_id = game.get("GameId")

            if not all([home, away, game_id]):
                print("⏩ Skipping game with missing team names.")
                continue

            score_game = next((g for g in scores_data if g.get("GameID") == game_id), None)

            if not score_game or score_game.get("Status") != "Final":
                print(f"⏩ {away} @ {home} — no final score found.")
                continue

            innings = score_game.get("Innings", [])
            home_score = score_game.get("HomeTeamRuns")
            away_score = score_game.get("AwayTeamRuns")


            if not isinstance(home_score, int) or not isinstance(away_score, int):
                print(f"⏩ {away} @ {home} — missing numeric score values.")
                continue

            if max(home_score, away_score) > 15 or home_score + away_score > 30:
                print(f"⚠️  Suspect score for {away} @ {home}: {away_score}-{home_score} → Skipping")
                print("🧾  Raw game data:", game)
                continue

            total_score = home_score + away_score
            actual_margin = home_score - away_score

            spread, total = None, None
            for book in game.get("PregameOdds", []):
                if book.get("Sportsbook") == "Scrambled":
                    spread = book.get("HomePointSpread")
                    total = book.get("OverUnder")
                    break

            if spread is None or total is None:
                print(f"⏩ {away} @ {home} — missing odds.")
                continue

            model_margin, model_total = simulate_model(home, away)
            spread_pick, spread_result = evaluate_spread(model_margin, spread, actual_margin)
            total_pick, total_result = evaluate_total(model_total, total, total_score)

            print(f"✅ {away} @ {home} — Score: {away_score}-{home_score} → Total: {total_score}")

            rows.append({
                "Date": current.date(),
                "Away Team": away,
                "Home Team": home,
                "Model Pick (Spread)": spread_pick,
                "Model Pick (Total)": total_pick,
                "Actual Margin": actual_margin,
                "Spread Result": spread_result,
                "Actual Total": total_score,
                "Total Result": total_result
            })

            time.sleep(REQUEST_DELAY)

        current += timedelta(days=1)

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Done! {len(df)} rows written to {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
