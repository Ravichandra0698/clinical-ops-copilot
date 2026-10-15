DROP INDEX IF EXISTS idx_visits_subject;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM visits WHERE subject_id = 'SUBJ0000001';

CREATE INDEX idx_visits_subject ON visits (subject_id);
ANALYZE visits;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM visits WHERE subject_id = 'SUBJ0000001';