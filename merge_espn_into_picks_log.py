import pandas as pd

PICKS_FILE = "picks_log.csv"
ESPN_FILE = "espn_scores.csv"
OUTPUT_FILE = "picks_log.csv"  # overwrite original

def evaluate_spread_result(pick, actual_margin):
    if pick == "Home -1.5":
        return "WIN" if actual_margin > 1.5 else "LOSS"
    elif pick == "Away +1.5":
        return "WIN" if actual_margin < -1.5 else "LOSS"
    return "LOSS"

def evaluate_total_result(pick, actual_total):
    try:
        target = float(pick.split()[-1])
        if pick.startswith("Over"):
            return "WIN" if actual_total > target else "LOSS"
        elif pick.startswith("Under"):
            return "WIN" if actual_total < target else "LOSS"
    except:
        return "LOSS"

def main():
    picks_df = pd.read_csv(PICKS_FILE)
    espn_df = pd.read_csv(ESPN_FILE)

    # Ensure consistent data types
    picks_df["Date"] = pd.to_datetime(picks_df["Date"]).dt.date
    espn_df["Date"] = pd.to_datetime(espn_df["Date"]).dt.date

    merged = pd.merge(
        picks_df,
        espn_df,
        on=["Date", "Away Team", "Home Team"],
        how="left"
    )

    # Update actuals
    merged["Actual Margin"] = merged["Home Score"] - merged["Away Score"]
    merged["Actual Total"] = merged["Home Score"] + merged["Away Score"]

    # Recalculate WIN/LOSS results
    merged["Spread Result"] = merged.apply(
        lambda row: evaluate_spread_result(row["Model Pick (Spread)"], row["Actual Margin"]), axis=1)

    merged["Total Result"] = merged.apply(
        lambda row: evaluate_total_result(row["Model Pick (Total)"], row["Actual Total"]), axis=1)

    # Drop the ESPN-only columns
    merged = merged.drop(columns=["Away Score", "Home Score", "Total"])

    # Write final corrected log
    merged.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ Updated {len(merged)} picks with official scores. Written to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
