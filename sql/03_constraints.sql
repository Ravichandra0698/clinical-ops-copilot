ALTER TABLE subjects ADD FOREIGN KEY (study_id) REFERENCES studies(study_id);
ALTER TABLE subjects ADD FOREIGN KEY (site_id)  REFERENCES trial_sites(site_id);
ALTER TABLE visits ADD FOREIGN KEY (subject_id) REFERENCES subjects(subject_id);
ALTER TABLE adverse_events ADD FOREIGN KEY (subject_id) REFERENCES subjects(subject_id);
ALTER TABLE adverse_events ADD FOREIGN KEY (visit_id)   REFERENCES visits(visit_id);

ANALYZE;