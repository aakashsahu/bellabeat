# Bellabeat Fitness Data Analytics — Case Study

## 1. Business Task
Analyze Fitbit smart-device usage data to uncover trends in how consumers use their
devices (activity, sleep, sedentary behavior, weight logging), then turn those trends
into high-level marketing recommendations for Bellabeat.

**Stakeholders:** Urška Sršen (Bellabeat co-founder/CCO), Sando Mur (co-founder), and the
Bellabeat marketing analytics team.

## 2. Data Sources
- **Fitbit Fitness Tracker Data** — public dataset on Kaggle (uploaded by user *Mobius*),
  originally collected via Amazon Mechanical Turk, 03/12/2016 – 05/12/2016.
- 33 users, CC0 license (Zenodo DOI: 10.5281/zenodo.53894).
- 16 CSV files used, spanning daily / hourly / minute / second granularity for activity,
  calories, intensity, steps, heart rate, sleep, and weight.

**Limitations:** no demographic data (age, sex, profession) to check representativeness;
no distance-unit documentation; inconsistent days-logged per user; small 2016 sample from
a third-party panel, not Bellabeat's own customers — treat findings as directional.

## 3. Tools Used
| Tool | Purpose |
|---|---|
| Python (`pandas`, `sqlite3`) | Data cleaning, transformation, DB construction |
| SQL (SQLite) | All analytical queries (`sql_insights.sql`) |
| Python (`matplotlib`, `seaborn`) | Visualizations |
| Streamlit | Interactive dashboard app |

## 4. Data Cleaning (documented step-by-step in `build_database.py` / `cleaning_log.txt`)
- Parsed all date/time fields to proper datetime types.
- Removed exact duplicate rows (3 in `sleepDay`, 0 elsewhere).
- Dropped 4 days with 0 steps **and** 0 calories (tracker not worn — not a real observation).
- Removed any rows with negative steps/calories (none found).
- Collapsed multiple same-day sleep entries (naps) down to the primary sleep record.
- Left the 97%-missing `Fat` column in `weightLogInfo` as NULL rather than imputing it.
- Flagged days with `SedentaryMinutes >= 1440` as `FullDaySedentary` (likely tracker not worn,
  not genuine 24-hr inactivity).
- Summarized the very large minute-level (1.3M+ rows) and heartrate-seconds (2.48M rows)
  files into per-user/per-hour aggregates rather than loading raw rows into the app, for
  performance — full detail is still computed once in `build_database.py`.
- Built a `daily_joined` table (`LEFT JOIN` of activity + sleep + weight on `Id`/date) for
  cross-metric analysis.

Run `python build_database.py` to regenerate `fitbit.db` and `cleaning_log.txt` from the
raw CSVs at any time — it's fully idempotent.

## 5. Summary of Analysis (see `sql_insights.sql` for the exact queries)
- Average 7,671 steps/day; only **32.4%** of tracked days hit the CDC's 10,000-step benchmark.
- Time breakdown: ~989 min/day sedentary vs. only ~35 min/day combined fairly+very active.
- Activity peaks **5–7 PM**.
- Average sleep: **6.99 hrs/night**, just under the 7-hr CDC minimum; only 46% of nights fall
  in the 7–9 hr recommended range.
- Only **24/33** users logged any sleep, and only **8/33** logged any weight — weight is the
  least-adopted feature.
- Higher-step days are associated with *less* sleep that same night (correlation only).
- User segmentation by average daily steps: 8 Sedentary, 9 Lightly Active, 9 Somewhat Active,
  7 Active.

## 6. Key Recommendations
1. **Close the sedentary gap** with move-reminders timed to the data-backed low-activity hours.
2. **Make weight logging effortless** (pair a Bellabeat scale with one-tap logging) — it's the
   weakest-adopted metric.
3. **Promote sleep tracking as a core habit** with a simple weekly sleep-score card.
4. **Anchor engagement features (challenges, notifications) around the 5–7 PM activity peak.**
5. **Segment marketing messaging by activity tier** rather than treating all users the same.

## 7. Project Structure
```
project/
├── build_database.py      # loads + cleans the raw CSVs into fitbit.db (run first)
├── fitbit.db               # generated SQLite database
├── cleaning_log.txt         # generated human-readable cleaning log
├── sql_insights.sql         # documented SQL analysis queries (12 business questions)
├── app.py                   # Streamlit dashboard (8 pages)
├── requirements.txt
└── README.md                 # this file
```

## 8. How to Run
```bash
pip install -r requirements.txt
python build_database.py      # builds fitbit.db (only needed once, or if CSVs change)
streamlit run app.py          # launches the dashboard at http://localhost:8501
```

## 9. Dashboard Pages
- **Overview** — KPIs, weekday step pattern, intensity-minute breakdown
- **Activity Patterns** — hourly pattern, per-user weekday heatmap, activity-segment pie chart
- **Sleep Analysis** — sleep duration by weekday, steps-vs-sleep relationship
- **Sedentary Behavior** — full-sedentary-day rate, per-user sedentary minutes
- **Weight & Engagement** — feature-adoption chart, engagement tiers, logged weight table
- **SQL Explorer** — run your own read-only SQL against the cleaned tables, live
- **Data & Cleaning Notes** — full documentation + the generated cleaning log
- **Recommendations** — findings and marketing recommendations, written out

## References
1. CDC — [Lifestyle Coach Facilitation Guide](https://www.cdc.gov/diabetes/prevention/pdf/postcurriculum_session8.pdf)
2. Harvard T.H. Chan School — [Moderate & Vigorous Physical Activity](https://www.hsph.harvard.edu/obesity-prevention-source/moderate-and-vigorous-physical-activity/)
3. Nike — [How Many Calories Should You Burn Daily](https://www.nike.com/a/how-many-calories-should-you-burn-daily)
4. CDC — [How Much Sleep Do I Need?](https://www.cdc.gov/sleep/about_sleep/how_much_sleep.html)
