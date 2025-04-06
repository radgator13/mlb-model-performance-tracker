import requests
import csv
from datetime import datetime, timedelta
import time

START_DATE = datetime(2025, 3, 27)
END_DATE = datetime.today() - timedelta(days=1)
OUTPUT_FILE = "espn_scores.csv"

def fetch_espn_json(date_str):
    url = f"https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates={date_str}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Failed to fetch {date_str}: {e}")
        return {}

def parse_espn_json(data, game_date):
    rows = []

    for event in data.get("events", []):
        try:
            competitors = event["competitions"][0]["competitors"]
            if len(competitors) != 2:
                continue

            away = next(c for c in competitors if c["homeAway"] == "away")
            home = next(c for c in competitors if c["homeAway"] == "home")

            away_team = away["team"]["abbreviation"]
            home_team = home["team"]["abbreviation"]
            away_score = int(away["score"])
            home_score = int(home["score"])
            total = away_score + home_score

            print(f"✅ {away_team} @ {home_team} — {away_score}-{home_score} → Total: {total}")
            rows.append({
                "Date": game_date,
                "Away Team": away_team,
                "Home Team": home_team,
                "Away Score": away_score,
                "Home Score": home_score,
                "Total": total
            })
        except Exception:
            continue

    return rows

def run_scraper():
    current = START_DATE
    all_rows = []

    while current <= END_DATE:
        date_str = current.strftime("%Y%m%d")
        print(f"\n🔄 Fetching {date_str}...")
        json_data = fetch_espn_json(date_str)
        daily_rows = parse_espn_json(json_data, current.date())
        all_rows.extend(daily_rows)
        time.sleep(1)
        current += timedelta(days=1)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Date", "Away Team", "Home Team", "Away Score", "Home Score", "Total"])
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n✅ Done! {len(all_rows)} games written to {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
