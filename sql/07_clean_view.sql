CREATE OR REPLACE VIEW visits_clean AS
SELECT visit_id, subject_id, visit_name, scheduled_date, actual_date, visit_status
FROM (
    SELECT v.visit_id, v.subject_id, v.visit_name, v.scheduled_date,
           v.actual_date, v.visit_status, s.consent_date,
           ROW_NUMBER() OVER (
               PARTITION BY v.subject_id, v.visit_name
               ORDER BY v.visit_id
           ) AS rn
    FROM visits v
    JOIN subjects s ON s.subject_id = v.subject_id
) 
WHERE rn = 1
  AND (actual_date IS NULL OR actual_date >= consent_date);

\echo '--- raw vs clean row counts'
SELECT (SELECT COUNT(*) FROM visits)       AS raw_visits,
       (SELECT COUNT(*) FROM visits_clean) AS clean_visits;

\echo '--- duplicates remaining in the clean view (should be 0)'
SELECT COUNT(*) AS duplicate_groups_in_clean
FROM (
    SELECT subject_id, visit_name
    FROM visits_clean
    GROUP BY subject_id, visit_name
    HAVING COUNT(*) > 1
) d;