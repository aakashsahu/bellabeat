"""
app.py
------
Bellabeat / Fitbit Fitness Data Analytics - Streamlit Dashboard

Run with:
    streamlit run app.py

Requires fitbit.db to already exist (run `python build_database.py` first).
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st

# ---------------------------------------------------------------------------
# Page config & styling
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Bellabeat Fitness Analytics", layout="wide", page_icon="📊")
sns.set_style("whitegrid")
sns.set_palette("Set2")

DB_PATH = "fitbit.db"


@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


@st.cache_data
def run_sql(query, params=None):
    """Run a SQL query against fitbit.db and return a DataFrame."""
    conn = get_connection()
    return pd.read_sql_query(query, conn, params=params)


WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
st.sidebar.title("📊 Bellabeat Analytics")
page = st.sidebar.radio(
    "Go to",
    [
        "Overview",
        "Activity Patterns",
        "Sleep Analysis",
        "Sedentary Behavior",
        "Weight & Engagement",
        "SQL Explorer",
        "Data & Cleaning Notes",
        "Recommendations",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Data: Fitbit Fitness Tracker Data (Kaggle, via Mobius), "
    "33 users, collected by Amazon Mechanical Turk, Apr-May 2016."
)

# ---------------------------------------------------------------------------
# OVERVIEW
# ---------------------------------------------------------------------------
if page == "Overview":
    st.title("Bellabeat: How Are Smart Device Users Behaving?")
    st.markdown(
        """
        **Business task:** Analyze smart-device fitness data to uncover usage trends that can
        inform Bellabeat's marketing strategy.
        """
    )

    kpis = run_sql("""
        SELECT
            COUNT(DISTINCT Id) AS users,
            ROUND(AVG(TotalSteps), 0) AS avg_steps,
            ROUND(AVG(Calories), 0) AS avg_calories,
            ROUND(100.0 * SUM(CASE WHEN TotalSteps >= 10000 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_10k
        FROM daily_activity
    """).iloc[0]

    sleep_kpi = run_sql("""
        SELECT ROUND(AVG(TotalMinutesAsleep)/60.0, 2) AS avg_sleep_hrs FROM sleep_day
    """).iloc[0]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Users tracked", int(kpis["users"]))
    c2.metric("Avg. daily steps", f"{int(kpis['avg_steps']):,}")
    c3.metric("Avg. daily calories", f"{int(kpis['avg_calories']):,}")
    c4.metric("Days hitting 10k steps", f"{kpis['pct_10k']}%")
    c5.metric("Avg. sleep / night", f"{sleep_kpi['avg_sleep_hrs']} hrs")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Average steps by weekday")
        df = run_sql("""
            SELECT Weekday, ROUND(AVG(TotalSteps),0) AS avg_steps
            FROM daily_activity GROUP BY Weekday
        """)
        df["Weekday"] = pd.Categorical(df["Weekday"], categories=WEEKDAY_ORDER, ordered=True)
        df = df.sort_values("Weekday")
        fig, ax = plt.subplots(figsize=(6, 4))
        sns.barplot(data=df, x="Weekday", y="avg_steps", ax=ax)
        ax.axhline(10000, color="red", linestyle="--", linewidth=1, label="CDC 10k goal")
        ax.set_xticklabels(ax.get_xticklabels(), rotation=40, ha="right")
        ax.set_ylabel("Avg. steps")
        ax.set_xlabel("")
        ax.legend()
        st.pyplot(fig)

    with col2:
        st.subheader("Time spent by activity intensity")
        df = run_sql("""
            SELECT
                ROUND(AVG(SedentaryMinutes),1) AS Sedentary,
                ROUND(AVG(LightlyActiveMinutes),1) AS "Lightly Active",
                ROUND(AVG(FairlyActiveMinutes),1) AS "Fairly Active",
                ROUND(AVG(VeryActiveMinutes),1) AS "Very Active"
            FROM daily_activity
        """).T.reset_index()
        df.columns = ["Category", "Minutes"]
        fig, ax = plt.subplots(figsize=(6, 4))
        sns.barplot(data=df, x="Category", y="Minutes", ax=ax)
        ax.set_xlabel("")
        for i, v in enumerate(df["Minutes"]):
            ax.text(i, v + 5, str(v), ha="center", fontsize=9)
        st.pyplot(fig)

    st.info(
        "Sedentary time dominates the day (~989 min ≈ 16.5 hrs average), while combined "
        "moderate-to-vigorous activity is under 35 minutes/day — this shapes the recommendations below."
    )

# ---------------------------------------------------------------------------
# ACTIVITY PATTERNS
# ---------------------------------------------------------------------------
elif page == "Activity Patterns":
    st.title("Activity Patterns")

    st.subheader("Hourly movement pattern (all users, all days)")
    df = run_sql("""
        SELECT Hour, ROUND(AVG(StepTotal),0) AS avg_steps, ROUND(AVG(Calories),1) AS avg_calories
        FROM hourly_activity GROUP BY Hour ORDER BY Hour
    """)
    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax2 = ax1.twinx()
    sns.barplot(data=df, x="Hour", y="avg_steps", ax=ax1, color="#8ecae6", label="Avg steps")
    sns.lineplot(data=df, x="Hour", y="avg_calories", ax=ax2, color="#e76f51", marker="o", label="Avg calories")
    ax1.set_ylabel("Avg. steps")
    ax2.set_ylabel("Avg. calories burnt")
    ax1.set_xlabel("Hour of day")
    st.pyplot(fig)
    st.caption("Activity peaks in the late afternoon / early evening (5-7 PM) — a natural notification window.")

    st.markdown("---")
    st.subheader("Per-user step pattern by weekday (heatmap)")
    df = run_sql("""
        SELECT Id, Weekday, ROUND(AVG(TotalSteps),0) AS avg_steps
        FROM daily_activity GROUP BY Id, Weekday
    """)
    pivot = df.pivot(index="Id", columns="Weekday", values="avg_steps")[WEEKDAY_ORDER]
    fig, ax = plt.subplots(figsize=(9, 8))
    sns.heatmap(pivot, cmap="YlOrRd", ax=ax, linewidths=0.3, cbar_kws={"label": "Avg steps"})
    st.pyplot(fig)

    st.markdown("---")
    st.subheader("User activity segmentation")
    df = run_sql("""
        SELECT Id, ROUND(AVG(TotalSteps),0) AS avg_steps,
        CASE
            WHEN AVG(TotalSteps) < 5000  THEN 'Sedentary'
            WHEN AVG(TotalSteps) < 7500  THEN 'Lightly Active'
            WHEN AVG(TotalSteps) < 10000 THEN 'Somewhat Active'
            ELSE 'Active'
        END AS segment
        FROM daily_activity GROUP BY Id
    """)
    seg_counts = df["segment"].value_counts().reindex(
        ["Sedentary", "Lightly Active", "Somewhat Active", "Active"]
    )
    col1, col2 = st.columns([1, 1])
    with col1:
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.pie(seg_counts, labels=seg_counts.index, autopct="%1.0f%%", startangle=90,
               colors=sns.color_palette("Set2"))
        ax.set_title("Users by activity segment (based on step-count classification*)")
        st.pyplot(fig)
    with col2:
        st.dataframe(df.sort_values("avg_steps"), use_container_width=True, height=400)
    st.caption("*Segment thresholds (Sedentary/Lightly/Somewhat/Active) are our own step-count "
               "buckets for this analysis, not an official CDC classification.")

# ---------------------------------------------------------------------------
# SLEEP
# ---------------------------------------------------------------------------
elif page == "Sleep Analysis":
    st.title("Sleep Analysis")

    kpis = run_sql("""
        SELECT ROUND(AVG(TotalMinutesAsleep)/60.0,2) AS avg_sleep,
               ROUND(AVG(TimeAwakeInBed),1) AS avg_awake,
               ROUND(100.0*SUM(CASE WHEN TotalMinutesAsleep BETWEEN 420 AND 540 THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_recommended
        FROM sleep_day
    """).iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg. sleep / night", f"{kpis['avg_sleep']} hrs")
    c2.metric("Avg. minutes awake in bed", f"{kpis['avg_awake']} min")
    c3.metric("Nights in 7-9 hr recommended range", f"{kpis['pct_recommended']}%")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Sleep duration by weekday")
        df = run_sql("""
            SELECT Weekday, ROUND(AVG(TotalMinutesAsleep)/60.0,2) AS avg_sleep_hrs
            FROM sleep_day GROUP BY Weekday
        """)
        df["Weekday"] = pd.Categorical(df["Weekday"], categories=WEEKDAY_ORDER, ordered=True)
        df = df.sort_values("Weekday")
        fig, ax = plt.subplots(figsize=(6, 4))
        sns.barplot(data=df, x="Weekday", y="avg_sleep_hrs", ax=ax)
        ax.axhline(7, color="green", linestyle="--", linewidth=1, label="7 hr min. guideline")
        ax.set_xticklabels(ax.get_xticklabels(), rotation=40, ha="right")
        ax.legend()
        st.pyplot(fig)

    with col2:
        st.subheader("Steps vs. sleep duration that night")
        df = run_sql("""
            SELECT
                CASE WHEN TotalSteps < 5000 THEN '<5k steps'
                     WHEN TotalSteps < 10000 THEN '5k-10k steps'
                     ELSE '10k+ steps' END AS bucket,
                ROUND(AVG(TotalMinutesAsleep)/60.0,2) AS avg_sleep_hrs
            FROM daily_joined WHERE TotalMinutesAsleep IS NOT NULL
            GROUP BY bucket
        """)
        order = ["<5k steps", "5k-10k steps", "10k+ steps"]
        df["bucket"] = pd.Categorical(df["bucket"], categories=order, ordered=True)
        df = df.sort_values("bucket")
        fig, ax = plt.subplots(figsize=(6, 4))
        sns.barplot(data=df, x="bucket", y="avg_sleep_hrs", ax=ax)
        st.pyplot(fig)
        st.caption("Higher-step days are associated with *less* sleep that night in this sample — "
                   "correlation, not proven causation (small, self-selected sample).")

    st.warning(
        f"Only {run_sql('SELECT COUNT(DISTINCT Id) n FROM sleep_day').iloc[0]['n']} of "
        f"{run_sql('SELECT COUNT(DISTINCT Id) n FROM daily_activity').iloc[0]['n']} users "
        "logged any sleep data at all — sleep tracking is a low-adoption feature in this dataset."
    )

# ---------------------------------------------------------------------------
# SEDENTARY BEHAVIOR
# ---------------------------------------------------------------------------
elif page == "Sedentary Behavior":
    st.title("Sedentary Behavior")

    df = run_sql("""
        SELECT SUM(CASE WHEN FullDaySedentary THEN 1 ELSE 0 END) AS full_days,
               COUNT(*) AS total_days
        FROM daily_activity
    """).iloc[0]
    st.metric(
        "Days recorded as 100% sedentary (1440 min)",
        f"{df['full_days']} / {df['total_days']} ({100*df['full_days']/df['total_days']:.1f}%)",
    )
    st.caption("These are likely days the tracker wasn't worn rather than true 24-hour inactivity.")

    st.subheader("Average sedentary minutes per user (sorted)")
    df = run_sql("""
        SELECT Id, ROUND(AVG(SedentaryMinutes),0) AS avg_sedentary
        FROM daily_activity GROUP BY Id ORDER BY avg_sedentary
    """)
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=df, x="Id", y="avg_sedentary", order=df.sort_values("avg_sedentary")["Id"],
                ax=ax, color="#e07a5f")
    ax.axhline(480, color="green", linestyle="--", label="8 hr baseline (sleep+rest)")
    ax.set_xticklabels([])
    ax.set_xlabel("Users (anonymized)")
    ax.set_ylabel("Avg. sedentary minutes/day")
    ax.legend()
    st.pyplot(fig)
    st.caption("About a third of users average well over 1,000 sedentary minutes/day (~17 hrs).")

# ---------------------------------------------------------------------------
# WEIGHT & ENGAGEMENT
# ---------------------------------------------------------------------------
elif page == "Weight & Engagement":
    st.title("Weight Logging & Device Engagement")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Feature adoption across the 33 users")
        df = run_sql("""
            SELECT
                (SELECT COUNT(DISTINCT Id) FROM daily_activity) AS "Activity",
                (SELECT COUNT(DISTINCT Id) FROM sleep_day) AS "Sleep",
                (SELECT COUNT(DISTINCT Id) FROM weight_log) AS "Weight"
        """).T.reset_index()
        df.columns = ["Feature", "Users"]
        fig, ax = plt.subplots(figsize=(5, 4))
        sns.barplot(data=df, x="Feature", y="Users", ax=ax)
        ax.axhline(33, color="gray", linestyle=":", label="All 33 users")
        for i, v in enumerate(df["Users"]):
            ax.text(i, v + 0.5, str(v), ha="center")
        ax.legend()
        st.pyplot(fig)
        st.caption("Weight logging has the steepest drop-off (8/33 users) — a clear opportunity "
                   "for Bellabeat to make weight tracking easier or more motivating.")

    with col2:
        st.subheader("Days logged per user (engagement tiers)")
        df = run_sql("""
            SELECT Id, COUNT(DISTINCT ActivityDate) AS days_logged,
            CASE
                WHEN COUNT(DISTINCT ActivityDate) >= 25 THEN 'High'
                WHEN COUNT(DISTINCT ActivityDate) >= 15 THEN 'Moderate'
                ELSE 'Low'
            END AS tier
            FROM daily_activity GROUP BY Id
        """)
        tier_counts = df["tier"].value_counts().reindex(["High", "Moderate", "Low"])
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.pie(tier_counts, labels=tier_counts.index, autopct="%1.0f%%", startangle=90,
               colors=sns.color_palette("Set2"))
        ax.set_title("Engagement tier (days logged out of ~31)")
        st.pyplot(fig)

    st.markdown("---")
    weight_df = run_sql("SELECT Id, Date, WeightKg, BMI FROM weight_log ORDER BY Id, Date")
    if not weight_df.empty:
        st.subheader("Logged weight entries")
        st.dataframe(weight_df, use_container_width=True)

# ---------------------------------------------------------------------------
# SQL EXPLORER
# ---------------------------------------------------------------------------
elif page == "SQL Explorer":
    st.title("SQL Explorer")
    st.markdown(
        "Run any read-only SQL query directly against the cleaned database "
        "(tables: `daily_activity`, `hourly_activity`, `sleep_day`, `weight_log`, "
        "`daily_joined`, `heartrate_hourly_avg`, `minute_sleep_state_summary`)."
    )
    default_query = "SELECT * FROM daily_activity LIMIT 20;"
    query = st.text_area("SQL query", value=default_query, height=120)
    if st.button("Run query"):
        q = query.strip().rstrip(";")
        if not q.lower().startswith("select"):
            st.error("Only SELECT queries are allowed here.")
        else:
            try:
                result = run_sql(q)
                st.success(f"{len(result)} rows returned")
                st.dataframe(result, use_container_width=True)
            except Exception as e:
                st.error(f"Query failed: {e}")

    with st.expander("See the full documented SQL insight queries (sql_insights.sql)"):
        st.code(open("sql_insights.sql").read(), language="sql")

# ---------------------------------------------------------------------------
# DATA & CLEANING NOTES
# ---------------------------------------------------------------------------
elif page == "Data & Cleaning Notes":
    st.title("Data Sources & Cleaning Documentation")

    st.subheader("Data source")
    st.markdown(
        """
        - **Source:** Fitbit Fitness Tracker Data, public dataset on Kaggle (uploaded by user *Mobius*).
        - **Collected by:** Amazon Mechanical Turk survey, 03/12/2016 - 05/12/2016.
        - **Scope:** 33 Fitbit users who consented to share personal tracker data
          (activity, heart rate, sleep) at second/minute/hour/day granularity.
        - **License:** CC0 (public domain) via Zenodo (DOI 10.5281/zenodo.53894).

        **Known limitations (carried over from the source case study):**
        - No demographic data (age, sex, height, profession) — can't check for bias or segment demographically.
        - No units specified for distance fields.
        - Inconsistent logging days per user; some users have 31 days (spans April + May), others fewer.
        - `SedentaryMinutes = 1440` on some days suggests the tracker wasn't worn, not 24 hrs of stillness.
        - Small, self-selected, Mechanical-Turk sample from 2016 — not necessarily representative of
          Bellabeat's actual customer base.
        """
    )

    st.subheader("Cleaning steps performed (build_database.py)")
    try:
        st.code(open("cleaning_log.txt").read())
    except FileNotFoundError:
        st.warning("Run `python build_database.py` to generate the cleaning log.")

# ---------------------------------------------------------------------------
# RECOMMENDATIONS
# ---------------------------------------------------------------------------
elif page == "Recommendations":
    st.title("Key Findings & Marketing Recommendations")

    st.subheader("Key findings")
    st.markdown(
        """
        1. **Most users fall short of the 10,000-step benchmark** — only ~32% of tracked days hit it,
           and average moderate-to-vigorous activity is under 35 min/day.
        2. **Sedentary time dominates** — ~989 min/day (~16.5 hrs) on average; ~8% of days are recorded
           as fully sedentary, likely reflecting the tracker not being worn.
        3. **Activity peaks 5-7 PM** — a natural window for reminder notifications or challenges.
        4. **Sleep is under-tracked and under the guideline** — only 24/33 users logged sleep at all, and
           average sleep (6.99 hrs) is just under the CDC's 7-hr minimum.
        5. **Weight logging has the weakest adoption** — only 8/33 users logged weight even once,
           the steepest drop-off of any feature.
        6. **Higher-step days correlate with less sleep** that same night in this sample — worth
           watching, though the sample can't establish causation.
        """
    )

    st.subheader("High-level recommendations for Bellabeat")
    st.markdown(
        """
        - **Close the sedentary gap with smart nudges:** trigger a gentle move-reminder after a
          detected long sedentary stretch, timed around the data-backed low-activity mid-morning window.
        - **Make weight logging effortless:** weight is the least-adopted metric — pair the Bellabeat
          scale/app with one-tap logging and light positive reinforcement (streaks, trends) rather
          than a manual daily entry.
        - **Promote sleep tracking as a core habit**, not an afterthought — surface a simple weekly
          sleep-score card, since fewer than half of nights fall in the recommended 7-9 hr range.
        - **Use the 5-7 PM activity peak** as the anchor time for Bellabeat's activity challenges,
          push notifications, and social/community features.
        - **Segment marketing messaging by activity tier** (Sedentary / Lightly Active / Somewhat
          Active / Active users each respond to different framing — e.g. habit-building for
          Sedentary users vs. performance framing for Active users).
        """
    )

    st.caption(
        "Caveat: this dataset is small (33 users), non-demographic, and from 2016 — treat these as "
        "directional hypotheses to validate against Bellabeat's own, larger and more recent user data."
    )
