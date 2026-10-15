CREATE TABLE studies (
    study_id            TEXT PRIMARY KEY,
    therapeutic_area    TEXT NOT NULL,
    phase               TEXT NOT NULL,
    planned_enrollment  INTEGER NOT NULL,
    status              TEXT NOT NULL
);

CREATE TABLE trial_sites (
    site_id              TEXT PRIMARY KEY,
    country              TEXT NOT NULL,
    region               TEXT NOT NULL,
    enrollment_capacity  INTEGER NOT NULL
);

CREATE TABLE subjects (
    subject_id      TEXT PRIMARY KEY,
    study_id        TEXT NOT NULL,
    site_id         TEXT NOT NULL,
    age             NUMERIC(4,1),
    sex             TEXT NOT NULL,
    arm             TEXT NOT NULL,
    consent_date    DATE NOT NULL,
    subject_status  TEXT NOT NULL
);

CREATE TABLE visits (
    visit_id        BIGINT PRIMARY KEY,
    subject_id      TEXT NOT NULL,
    visit_name      TEXT NOT NULL,
    scheduled_date  DATE NOT NULL,
    actual_date     DATE,
    visit_status    TEXT NOT NULL
);

CREATE TABLE adverse_events (
    ae_id          BIGINT PRIMARY KEY,
    subject_id     TEXT NOT NULL,
    visit_id       BIGINT NOT NULL,
    ae_term        TEXT NOT NULL,
    severity       TEXT NOT NULL,
    is_serious     BOOLEAN NOT NULL,
    onset_date     DATE NOT NULL,
    reported_date  DATE NOT NULL
);