SELECT 'studies' AS table_name, COUNT(*) FROM studies
UNION ALL SELECT 'trial_sites', COUNT(*) FROM trial_sites
UNION ALL SELECT 'subjects', COUNT(*) FROM subjects
UNION ALL SELECT 'visits', COUNT(*) FROM visits
UNION ALL SELECT 'adverse_events', COUNT(*) FROM adverse_events;

SELECT site_id,
       COUNT(*) AS subjects,
       ROUND(100.0 * AVG((subject_status = 'DISCONTINUED')::int), 1) AS dropout_pct
FROM subjects
GROUP BY site_id
HAVING COUNT(*) >= 50
ORDER BY dropout_pct DESC
LIMIT 5;