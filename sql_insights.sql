-- =============================================================================
-- sql_insights.sql
-- SQL Analysis for: How Can a Wellness Technology Company (Bellabeat) Play It Smart?
-- Run against fitbit.db (build with build_database.py first)
-- Usage:  sqlite3 fitbit.db < sql_insights.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Q1. How active are users overall? (CDC guideline reference: 10,000 steps/day)
-- -----------------------------------------------------------------------------
SELECT
    ROUND(AVG(TotalSteps), 0)                                   AS avg_daily_steps,
    ROUND(100.0 * SUM(CASE WHEN TotalSteps >= 10000 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_days_hit_10k,
    ROUND(AVG(Calories), 0)                                     AS avg_daily_calories
FROM daily_activity;

-- -----------------------------------------------------------------------------
-- Q2. Which weekdays are users most / least active? (steps & calories)
-- -----------------------------------------------------------------------------
SELECT
    Weekday,
    WeekdayNum,
    ROUND(AVG(TotalSteps), 0)   AS avg_steps,
    ROUND(AVG(Calories), 0)     AS avg_calories,
    ROUND(AVG(VeryActiveMinutes + FairlyActiveMinutes + LightlyActiveMinutes), 1) AS avg_active_minutes
FROM daily_activity
GROUP BY Weekday, WeekdayNum
ORDER BY WeekdayNum;

-- -----------------------------------------------------------------------------
-- Q3. How is activity-intensity time distributed? (sedentary vs light vs fair vs very active)
-- -----------------------------------------------------------------------------
SELECT
    ROUND(AVG(SedentaryMinutes), 1)      AS avg_sedentary_min,
    ROUND(AVG(LightlyActiveMinutes), 1)  AS avg_lightly_active_min,
    ROUND(AVG(FairlyActiveMinutes), 1)   AS avg_fairly_active_min,
    ROUND(AVG(VeryActiveMinutes), 1)     AS avg_very_active_min
FROM daily_activity;

-- -----------------------------------------------------------------------------
-- Q4. Per-user engagement segmentation: how many users are highly sedentary?
--     (avg sedentary minutes >= 1000/day ~ 16.7 hrs -> "Sedentary" segment)
-- -----------------------------------------------------------------------------
SELECT
    Id,
    ROUND(AVG(SedentaryMinutes), 1) AS avg_sedentary_min,
    ROUND(AVG(TotalSteps), 0)       AS avg_steps,
    CASE
        WHEN AVG(TotalSteps) < 5000  THEN 'Sedentary'
        WHEN AVG(TotalSteps) < 7500  THEN 'Lightly Active'
        WHEN AVG(TotalSteps) < 10000 THEN 'Somewhat Active'
        ELSE 'Active'
    END AS activity_segment
FROM daily_activity
GROUP BY Id
ORDER BY avg_steps;

-- Segment counts (for the dashboard's user-segmentation chart)
SELECT activity_segment, COUNT(*) AS num_users FROM (
    SELECT Id,
        CASE
            WHEN AVG(TotalSteps) < 5000  THEN 'Sedentary'
            WHEN AVG(TotalSteps) < 7500  THEN 'Lightly Active'
            WHEN AVG(TotalSteps) < 10000 THEN 'Somewhat Active'
            ELSE 'Active'
        END AS activity_segment
    FROM daily_activity GROUP BY Id
) GROUP BY activity_segment;

-- -----------------------------------------------------------------------------
-- Q5. What time of day do people move the most? (hourly step/calorie pattern)
-- -----------------------------------------------------------------------------
SELECT
    Hour,
    ROUND(AVG(StepTotal), 0)  AS avg_steps,
    ROUND(AVG(Calories), 1)   AS avg_calories,
    ROUND(AVG(TotalIntensity), 2) AS avg_intensity
FROM hourly_activity
GROUP BY Hour
ORDER BY Hour;

-- -----------------------------------------------------------------------------
-- Q6. Sleep: how much are users actually sleeping, and how efficient is it?
--     (CDC recommends 7-9 hrs = 420-540 min for adults)
-- -----------------------------------------------------------------------------
SELECT
    ROUND(AVG(TotalMinutesAsleep) / 60.0, 2) AS avg_sleep_hours,
    ROUND(AVG(TotalTimeInBed) / 60.0, 2)     AS avg_time_in_bed_hours,
    ROUND(AVG(TimeAwakeInBed), 1)            AS avg_minutes_awake_in_bed,
    ROUND(100.0 * SUM(CASE WHEN TotalMinutesAsleep BETWEEN 420 AND 540 THEN 1 ELSE 0 END) / COUNT(*), 1)
                                              AS pct_nights_in_recommended_range
FROM sleep_day;

-- Sleep by weekday
SELECT
    Weekday,
    ROUND(AVG(TotalMinutesAsleep) / 60.0, 2) AS avg_sleep_hours
FROM sleep_day
GROUP BY Weekday;

-- -----------------------------------------------------------------------------
-- Q7. Relationship between activity and sleep: do more active days correlate
--     with more/less sleep that night? (same-day join)
-- -----------------------------------------------------------------------------
SELECT
    CASE
        WHEN TotalSteps < 5000  THEN '<5k steps'
        WHEN TotalSteps < 10000 THEN '5k-10k steps'
        ELSE '10k+ steps'
    END AS step_bucket,
    ROUND(AVG(TotalMinutesAsleep) / 60.0, 2) AS avg_sleep_hours,
    COUNT(*) AS n_days
FROM daily_joined
WHERE TotalMinutesAsleep IS NOT NULL
GROUP BY step_bucket;

-- -----------------------------------------------------------------------------
-- Q8. Sedentary minutes vs sleep duration (does sitting all day hurt sleep?)
-- -----------------------------------------------------------------------------
SELECT
    ROUND(AVG(CASE WHEN SedentaryMinutes >= 1000 THEN TotalMinutesAsleep END) / 60.0, 2) AS sleep_hrs_high_sedentary,
    ROUND(AVG(CASE WHEN SedentaryMinutes <  1000 THEN TotalMinutesAsleep END) / 60.0, 2) AS sleep_hrs_lower_sedentary
FROM daily_joined
WHERE TotalMinutesAsleep IS NOT NULL;

-- -----------------------------------------------------------------------------
-- Q9. Device engagement: how many distinct days did each user actually log data?
--     (proxy for engagement / habit formation - key for Bellabeat's marketing angle)
-- -----------------------------------------------------------------------------
SELECT
    Id,
    COUNT(DISTINCT ActivityDate) AS days_logged,
    CASE
        WHEN COUNT(DISTINCT ActivityDate) >= 25 THEN 'High engagement'
        WHEN COUNT(DISTINCT ActivityDate) >= 15 THEN 'Moderate engagement'
        ELSE 'Low engagement'
    END AS engagement_tier
FROM daily_activity
GROUP BY Id
ORDER BY days_logged DESC;

-- -----------------------------------------------------------------------------
-- Q10. Feature adoption gap: what fraction of the 33 users logged sleep at all,
--      and weight at all? (shows which Bellabeat features see low opt-in)
-- -----------------------------------------------------------------------------
SELECT
    (SELECT COUNT(DISTINCT Id) FROM daily_activity) AS total_users,
    (SELECT COUNT(DISTINCT Id) FROM sleep_day)       AS users_logging_sleep,
    (SELECT COUNT(DISTINCT Id) FROM weight_log)      AS users_logging_weight;

-- -----------------------------------------------------------------------------
-- Q11. Full-day-sedentary flag: how often does the tracker record 1440 min
--      sedentary (i.e. it likely wasn't worn / user was totally inactive)?
-- -----------------------------------------------------------------------------
SELECT
    SUM(CASE WHEN FullDaySedentary THEN 1 ELSE 0 END) AS full_sedentary_days,
    COUNT(*) AS total_days,
    ROUND(100.0 * SUM(CASE WHEN FullDaySedentary THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_of_days
FROM daily_activity;

-- -----------------------------------------------------------------------------
-- Q12. Heart-rate pattern by hour (for the ~14 users with HR data) - resting vs active hours
-- -----------------------------------------------------------------------------
SELECT
    Hour,
    ROUND(AVG(AvgHeartRate), 1) AS avg_heart_rate
FROM heartrate_hourly_avg
GROUP BY Hour
ORDER BY Hour;
