import streamlit as st
import pandas as pd
import plotly.express as px
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
        if pd.isnull(value):
            return "—"
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
    "Win % Chart Range", ["Last 7 Days", "Last 14 Days", "Full Season"],
    horizontal=True,
    index=2
)

# Valid results
valid_chart_df = df[df["Spread Result"].isin(["WIN", "LOSS"]) | df["Total Result"].isin(["WIN", "LOSS"])].copy()
valid_chart_df["Day"] = valid_chart_df["Date"].dt.floor("D")

# Filter by range
if range_option == "Last 7 Days":
    chart_df = valid_chart_df[valid_chart_df["Day"] >= pd.to_datetime(selected_date) - pd.Timedelta(days=6)]
elif range_option == "Last 14 Days":
    chart_df = valid_chart_df[valid_chart_df["Day"] >= pd.to_datetime(selected_date) - pd.Timedelta(days=13)]
else:
    chart_df = valid_chart_df.copy()

# Compute win %
def compute_win_rate(day_df):
    date = day_df["Day"].iloc[0]
    s_wins = (day_df["Spread Result"] == "WIN").sum()
    s_total = day_df["Spread Result"].isin(["WIN", "LOSS"]).sum()
    t_wins = (day_df["Total Result"] == "WIN").sum()
    t_total = day_df["Total Result"].isin(["WIN", "LOSS"]).sum()
    return {
        "Date": date,
        "Spread Win %": s_wins / s_total * 100 if s_total else 0.0,
        "Total Win %": t_wins / t_total * 100 if t_total else 0.0,
    }

# Daily win history
grouped = chart_df.groupby("Day")
actual_history = pd.DataFrame([compute_win_rate(day) for _, day in grouped])
actual_history["Date"] = pd.to_datetime(actual_history["Date"], errors="coerce")

# Merge full date range
full_range = pd.date_range(SEASON_START, datetime.today().date(), freq="D")
history = pd.DataFrame({"Date": full_range})
history = pd.merge(history, actual_history, on="Date", how="left")
history["Spread Win %"] = history["Spread Win %"].fillna(0)
history["Total Win %"] = history["Total Win %"].fillna(0)

# Find most recent non-zero entry
non_zero = history[(history["Spread Win %"] > 0) | (history["Total Win %"] > 0)]
latest = non_zero.iloc[-1] if not non_zero.empty else {}

# Display latest values (NOT just today if today = 0%)
col1, col2 = st.columns(2)
col1.metric("Spread Win % (Latest)", format_percent(latest.get("Spread Win %")))
col2.metric("Total Win % (Latest)", format_percent(latest.get("Total Win %")))

# === PLOTLY CHART (Final Version) ===
# === 📊 PLOTLY CHART (Final Enhancement) ===
long_df = history.melt(
    id_vars=["Date"],
    value_vars=["Spread Win %", "Total Win %"],
    var_name="Metric",
    value_name="Win %"
)

fig = px.line(
    long_df,
    x="Date",
    y="Win %",
    color="Metric",
    title="Daily Win % Over Time",
    markers=True,
    hover_data={"Win %": ".1f", "Date": True, "Metric": True}
)

# Add horizontal reference line at 0%
fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")

# Improve layout
fig.update_layout(
    xaxis=dict(
        title="Date",
        tickformat="%b %d",
        tickangle=-45,
        showgrid=True,
        showline=True,
        tickfont=dict(size=10)
    ),
    yaxis=dict(
        title="Win %",
        range=[-5, 105],  # pad for visibility of points at 0 and 100
        showgrid=True
    ),
    legend=dict(orientation="h", yanchor="bottom", y=1.1, x=0),
    margin=dict(l=40, r=20, t=50, b=80)
)

st.plotly_chart(fig, use_container_width=True)

