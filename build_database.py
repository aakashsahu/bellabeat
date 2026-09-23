"""
build_database.py
------------------
Loads the raw Fitbit/Bellabeat CSV export, documents & performs data-cleaning
steps, and writes a single clean SQLite database (fitbit.db) that the
Streamlit app and SQL insight queries run against.

Run once (or whenever the source CSVs change):
    python build_database.py
"""

import sqlite3
import pandas as pd
import numpy as np
import os

DB_PATH = "fitbit.db"
CSV_DIR = "."

# ---------------------------------------------------------------------------
# 1. Remove any existing DB so this script is safely re-runnable
# ---------------------------------------------------------------------------
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
conn = sqlite3.connect(DB_PATH)

log = []  # collects a human-readable cleaning log we also save to disk


def note(msg):
    print(msg)
    log.append(msg)


# ---------------------------------------------------------------------------
# 2. Load core tables we will actually use in the app
#    (minute-level / heartrate-seconds files are extremely large - 1.3M-2.5M
#    rows each - and duplicate information already summarized in the hourly
#    and daily tables. We load them separately, in build_minute_summary(),
#    only to produce a couple of aggregated insights, not row-by-row.)
# ---------------------------------------------------------------------------
daily = pd.read_csv(f"{CSV_DIR}/dailyActivity_merged.csv")
hourly_cal = pd.read_csv(f"{CSV_DIR}/hourlyCalories_merged.csv")
hourly_int = pd.read_csv(f"{CSV_DIR}/hourlyIntensities_merged.csv")
hourly_steps = pd.read_csv(f"{CSV_DIR}/hourlySteps_merged.csv")
sleep = pd.read_csv(f"{CSV_DIR}/sleepDay_merged.csv")
weight = pd.read_csv(f"{CSV_DIR}/weightLogInfo_merged.csv")

note(f"Loaded dailyActivity_merged: {len(daily)} rows, {daily['Id'].nunique()} unique users")
note(f"Loaded hourlyCalories/Intensities/Steps: {len(hourly_cal)} rows each")
note(f"Loaded sleepDay_merged: {len(sleep)} rows, {sleep['Id'].nunique()} unique users")
note(f"Loaded weightLogInfo_merged: {len(weight)} rows, {weight['Id'].nunique()} unique users")

# ---------------------------------------------------------------------------
# 3. Cleaning: dailyActivity
# ---------------------------------------------------------------------------
# 3a. Parse dates
daily["ActivityDate"] = pd.to_datetime(daily["ActivityDate"], format="%m/%d/%Y")

# 3b. Duplicate rows
dupes = daily.duplicated().sum()
daily = daily.drop_duplicates()
note(f"dailyActivity: dropped {dupes} exact duplicate rows")

# 3c. Drop rows where TotalSteps = 0 AND Calories = 0 (device not worn at all
#     that day -> not a real observation, would distort averages)
zero_mask = (daily["TotalSteps"] == 0) & (daily["Calories"] == 0)
note(f"dailyActivity: removing {zero_mask.sum()} rows with 0 steps AND 0 calories (tracker not worn)")
daily = daily[~zero_mask]

# 3d. Sanity bounds - remove physiologically impossible values (data-entry
#     errors), keep everything else as-is per the source documentation
before = len(daily)
daily = daily[(daily["Calories"] >= 0) & (daily["TotalSteps"] >= 0)]
note(f"dailyActivity: removed {before - len(daily)} rows with negative Calories/Steps")

# 3e. Add weekday column for weekday-pattern analysis
daily["Weekday"] = daily["ActivityDate"].dt.day_name()
daily["WeekdayNum"] = daily["ActivityDate"].dt.dayofweek  # Monday=0

# 3f. Flag "fully sedentary" days (>=1440 sedentary minutes = tracker
#     essentially not worn / not moved), per case-study observation
daily["FullDaySedentary"] = daily["SedentaryMinutes"] >= 1440

daily.to_sql("daily_activity", conn, index=False, if_exists="replace")
note(f"daily_activity table written: {len(daily)} rows")

# ---------------------------------------------------------------------------
# 4. Cleaning: hourly tables -> merge into one hourly_activity table
# ---------------------------------------------------------------------------
for df, col in [(hourly_cal, "ActivityHour"), (hourly_int, "ActivityHour"), (hourly_steps, "ActivityHour")]:
    df[col] = pd.to_datetime(df[col], format="%m/%d/%Y %I:%M:%S %p")

hourly = hourly_cal.merge(hourly_int, on=["Id", "ActivityHour"]).merge(
    hourly_steps, on=["Id", "ActivityHour"]
)
dupes = hourly.duplicated(subset=["Id", "ActivityHour"]).sum()
hourly = hourly.drop_duplicates(subset=["Id", "ActivityHour"])
note(f"hourly_activity: merged Calories+Intensities+Steps, dropped {dupes} duplicate (Id, Hour) rows")

hourly["Hour"] = hourly["ActivityHour"].dt.hour
hourly["Weekday"] = hourly["ActivityHour"].dt.day_name()
hourly.to_sql("hourly_activity", conn, index=False, if_exists="replace")
note(f"hourly_activity table written: {len(hourly)} rows")

# ---------------------------------------------------------------------------
# 5. Cleaning: sleep
# ---------------------------------------------------------------------------
sleep["SleepDay"] = pd.to_datetime(sleep["SleepDay"], format="%m/%d/%Y %I:%M:%S %p")
dupes = sleep.duplicated().sum()
sleep = sleep.drop_duplicates()
note(f"sleepDay: dropped {dupes} exact duplicate rows")

# Multiple sleep records per day (naps) -> keep only the main sleep record
# (TotalMinutesAsleep max per Id/day) to avoid double counting in daily joins
sleep_main = sleep.sort_values("TotalMinutesAsleep", ascending=False).drop_duplicates(
    subset=["Id", "SleepDay"], keep="first"
)
note(f"sleepDay: collapsed multiple same-day sleep records down to 1/day where present "
     f"({len(sleep) - len(sleep_main)} secondary nap records set aside)")

sleep_main["Weekday"] = sleep_main["SleepDay"].dt.day_name()
sleep_main["TimeAwakeInBed"] = sleep_main["TotalTimeInBed"] - sleep_main["TotalMinutesAsleep"]
sleep_main.to_sql("sleep_day", conn, index=False, if_exists="replace")
note(f"sleep_day table written: {len(sleep_main)} rows, {sleep_main['Id'].nunique()} unique users "
     f"(only {sleep_main['Id'].nunique()}/33 users logged sleep at all)")

# ---------------------------------------------------------------------------
# 6. Cleaning: weight log
# ---------------------------------------------------------------------------
weight["Date"] = pd.to_datetime(weight["Date"], format="%m/%d/%Y %I:%M:%S %p")
weight["Fat"] = weight["Fat"].where(weight["Fat"].notna(), np.nan)  # mostly missing - keep null, don't impute
note(f"weightLogInfo: 'Fat' column is {weight['Fat'].isna().mean():.0%} missing - left as NULL, not imputed")
weight.to_sql("weight_log", conn, index=False, if_exists="replace")
note(f"weight_log table written: {len(weight)} rows, {weight['Id'].nunique()} unique users "
     f"(only {weight['Id'].nunique()}/33 users logged weight at all)")

# ---------------------------------------------------------------------------
# 7. Build a wide "daily_joined" table (activity + sleep + weight) for
#    convenient cross-metric SQL/dashboard queries
# ---------------------------------------------------------------------------
conn.execute("""
CREATE TABLE daily_joined AS
SELECT
    a.Id,
    a.ActivityDate,
    a.Weekday,
    a.WeekdayNum,
    a.TotalSteps,
    a.TotalDistance,
    a.VeryActiveMinutes,
    a.FairlyActiveMinutes,
    a.LightlyActiveMinutes,
    a.SedentaryMinutes,
    a.FullDaySedentary,
    a.Calories,
    s.TotalMinutesAsleep,
    s.TotalTimeInBed,
    s.TimeAwakeInBed,
    w.WeightKg,
    w.BMI
FROM daily_activity a
LEFT JOIN sleep_day s
    ON a.Id = s.Id AND a.ActivityDate = s.SleepDay
LEFT JOIN weight_log w
    ON a.Id = w.Id AND a.ActivityDate = date(w.Date)
""")
note("daily_joined table created: LEFT JOIN of daily_activity + sleep_day + weight_log on (Id, Date)")

# ---------------------------------------------------------------------------
# 8. Minute-level files: summarize only (don't load raw rows into the app)
# ---------------------------------------------------------------------------
minute_sleep = pd.read_csv(f"{CSV_DIR}/minuteSleep_merged.csv")
minute_sleep["date"] = pd.to_datetime(minute_sleep["date"], format="%m/%d/%Y %I:%M:%S %p")
# value: 1=asleep, 2=restless, 3=awake (Fitbit sleep-stage coding)
sleep_state_summary = (
    minute_sleep.groupby("value").size().rename("minute_count").reset_index()
)
sleep_state_summary.to_sql("minute_sleep_state_summary", conn, index=False, if_exists="replace")
note(f"minuteSleep ({len(minute_sleep)} rows) summarized into sleep-state minute counts only")

hr = pd.read_csv(f"{CSV_DIR}/heartrate_seconds_merged.csv")
hr["Time"] = pd.to_datetime(hr["Time"], format="%m/%d/%Y %I:%M:%S %p")
hr["Hour"] = hr["Time"].dt.hour
hr_hourly = hr.groupby(["Id", "Hour"])["Value"].mean().reset_index().rename(columns={"Value": "AvgHeartRate"})
hr_hourly.to_sql("heartrate_hourly_avg", conn, index=False, if_exists="replace")
note(f"heartrate_seconds ({len(hr)} rows, {hr['Id'].nunique()} users with HR data) "
     f"aggregated to avg heart rate per user per hour-of-day")

conn.commit()

# ---------------------------------------------------------------------------
# 9. Save cleaning log to disk (used in the report / Streamlit "Data & Cleaning" tab)
# ---------------------------------------------------------------------------
with open("cleaning_log.txt", "w") as f:
    f.write("\n".join(log))

print("\nDone. Database written to", DB_PATH)
print("Tables:", [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()])
conn.close()
