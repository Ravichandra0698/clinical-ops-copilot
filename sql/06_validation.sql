\echo '--- 1. Duplicate visits (same subject + visit name)'
SELECT COUNT(*) AS duplicate_groups, SUM(n - 1) AS extra_rows
FROM (
    SELECT subject_id, visit_name, COUNT(*) AS n
    FROM visits
    GROUP BY subject_id, visit_name
    HAVING COUNT(*) > 1
) d;

\echo '--- 2. Visits dated before the subject consented'
SELECT COUNT(*) AS visits_before_consent
FROM visits v
JOIN subjects s ON s.subject_id = v.subject_id
WHERE v.actual_date < s.consent_date;

\echo '--- 3. Missing ages'
SELECT COUNT(*) FILTER (WHERE age IS NULL) AS missing_age,
       ROUND(100.0 * COUNT(*) FILTER (WHERE age IS NULL) / COUNT(*), 2) AS missing_pct
FROM subjects;

\echo '--- 4. Missed visits, and status vs date consistency'
SELECT COUNT(*) FILTER (WHERE visit_status = 'MISSED') AS missed_visits,
       ROUND(100.0 * COUNT(*) FILTER (WHERE visit_status = 'MISSED') / COUNT(*), 2) AS missed_pct,
       COUNT(*) FILTER (WHERE (actual_date IS NULL) <> (visit_status = 'MISSED')) AS inconsistent_rows
FROM visits;

\echo '--- 5. Average days late by site (top 5)'
SELECT s.site_id,
       COUNT(*) AS visits,
       ROUND(AVG(v.actual_date - v.scheduled_date), 2) AS avg_days_late
FROM visits v
JOIN subjects s ON s.subject_id = v.subject_id
WHERE v.visit_status = 'COMPLETED' AND v.actual_date >= s.consent_date
GROUP BY s.site_id
HAVING COUNT(*) >= 200
ORDER BY avg_days_late DESC
LIMIT 5;

\echo '--- 6. Adverse event reporting lag by site (top 5)'
SELECT s.site_id,
       COUNT(*) AS adverse_events,
       ROUND(AVG(a.reported_date - a.onset_date), 2) AS avg_report_lag_days
FROM adverse_events a
JOIN subjects s ON s.subject_id = a.subject_id
GROUP BY s.site_id
HAVING COUNT(*) >= 30
ORDER BY avg_report_lag_days DESC
LIMIT 5;

\echo '--- 7. Serious adverse events reported late (more than 1 day)'
SELECT COUNT(*) AS serious_aes,
       COUNT(*) FILTER (WHERE reported_date - onset_date > 1) AS reported_late
FROM adverse_events
WHERE is_serious;