"""
Synthetic pharma clinical-trial operations dataset (fictional sponsor).

All data is fabricated: no real subjects, sites, studies, or sponsor data.
Reproducible: same SEED -> same data.

Usage:
    python generate_pharma_data.py                  # ~1.0M visits
    python generate_pharma_data.py --subjects 20000 # quick test
    python generate_pharma_data.py --out pharma_data

Tables (CSV):
    studies            60
    trial_sites        800
    subjects           170,000 (default)
    visits             ~1.0M
    adverse_events     ~120K
    kpi_definitions.md glossary for RAG

Deliberate flaws (for validation / SQL / ML / agent days):
    - ~0.5% duplicate visits
    - ~0.5% visits dated before the subject's consent date (impossible)
    - ~1% missing subject age
    - 2 sites (SITE0034, SITE0412): late visits, high dropout, late AE reporting
    - ~4% missed visits
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 7
AREAS = ["Oncology", "Cardiology", "Immunology", "Infectious Disease",
         "Neuroscience", "Rare Disease", "Vaccines"]
COUNTRIES = [("US", "North America"), ("CA", "North America"), ("GB", "Europe"),
             ("DE", "Europe"), ("FR", "Europe"), ("ES", "Europe"),
             ("JP", "APAC"), ("IN", "APAC"), ("AU", "APAC"), ("BR", "LATAM")]
VISITS = [("SCREENING", 0), ("BASELINE", 7), ("WEEK2", 21), ("WEEK4", 35),
          ("WEEK8", 63), ("WEEK12", 91), ("WEEK24", 175), ("FOLLOWUP", 203)]
AE_TERMS = ["Headache", "Nausea", "Fatigue", "Dizziness", "Diarrhea", "Rash",
            "Injection site pain", "Pyrexia", "Insomnia", "Cough", "Back pain",
            "Vomiting", "Arthralgia", "Hypertension", "Anemia"]
BAD_SITES = [33, 411]  # zero-based positions -> SITE0034, SITE0412


def build_studies(rng):
    n = 60
    phase = rng.choice(["I", "II", "III", "IV"], n, p=[0.15, 0.30, 0.45, 0.10])
    planned = pd.Series(phase).map({"I": 60, "II": 300, "III": 2500, "IV": 1200}).values
    planned = (planned * rng.uniform(0.6, 1.5, n)).astype(int)
    return pd.DataFrame({
        "study_id": [f"STUDY{i:03d}" for i in range(1, n + 1)],
        "therapeutic_area": rng.choice(AREAS, n),
        "phase": phase,
        "planned_enrollment": planned,
        "status": rng.choice(["ENROLLING", "ACTIVE_NOT_ENROLLING", "COMPLETED"], n, p=[0.35, 0.35, 0.30]),
    })


def build_sites(rng):
    n = 800
    c = rng.choice(len(COUNTRIES), n, p=[0.35, 0.05, 0.10, 0.10, 0.07, 0.07, 0.10, 0.06, 0.05, 0.05])
    return pd.DataFrame({
        "site_id": [f"SITE{i:04d}" for i in range(1, n + 1)],
        "country": [COUNTRIES[i][0] for i in c],
        "region": [COUNTRIES[i][1] for i in c],
        "enrollment_capacity": rng.integers(10, 400, n),
    })


def build_subjects(rng, n, studies, sites):
    sw = studies["planned_enrollment"].values * (rng.pareto(2.5, len(studies)) + 1)
    site_w = rng.pareto(1.8, len(sites)) + 1
    site_idx = rng.choice(len(sites), n, p=site_w / site_w.sum())
    study_idx = rng.choice(len(studies), n, p=sw / sw.sum())
    consent = np.datetime64("2022-01-01") + rng.integers(0, 1360, n).astype("timedelta64[D]")
    bad = np.isin(site_idx, BAD_SITES)
    p_good = np.array([0.12, 0.13, 0.57, 0.18])
    p_bad = np.array([0.10, 0.45, 0.30, 0.15])
    labels = np.array(["SCREEN_FAILED", "DISCONTINUED", "COMPLETED", "ENROLLED"])
    status = np.where(bad, labels[rng.choice(4, n, p=p_bad)], labels[rng.choice(4, n, p=p_good)])
    age = np.clip(rng.normal(55, 15, n), 18, 90).astype(float)
    age[rng.random(n) < 0.01] = np.nan
    df = pd.DataFrame({
        "subject_id": [f"SUBJ{i:07d}" for i in range(1, n + 1)],
        "study_id": studies["study_id"].values[study_idx],
        "site_id": sites["site_id"].values[site_idx],
        "age": age,
        "sex": rng.choice(["F", "M"], n, p=[0.48, 0.52]),
        "arm": rng.choice(["TREATMENT", "PLACEBO"], n),
        "consent_date": consent,
        "subject_status": status,
    })
    return df, site_idx


def build_visits(rng, subjects, site_idx):
    n = len(subjects)
    st = subjects["subject_status"].values
    nv = np.select(
        [st == "SCREEN_FAILED", st == "DISCONTINUED", st == "COMPLETED"],
        [np.ones(n, int), rng.integers(2, 7, n), np.full(n, 8)],
        default=rng.integers(3, 9, n),
    )
    total = nv.sum()
    subj_idx = np.repeat(np.arange(n), nv)
    vis_idx = np.arange(total) - np.repeat(np.cumsum(nv) - nv, nv)
    offsets = np.array([o for _, o in VISITS])
    names = np.array([v for v, _ in VISITS])

    consent = subjects["consent_date"].values[subj_idx]
    scheduled = consent + offsets[vis_idx].astype("timedelta64[D]")
    bad = np.isin(site_idx[subj_idx], BAD_SITES)
    delay = np.round(rng.normal(0, 2.5, total)).astype(int) + np.where(bad, 6, 0)
    delay = np.where(vis_idx == 0, np.maximum(delay, 0), delay)  # screening cannot precede consent
    actual = scheduled + delay.astype("timedelta64[D]")

    missed = (rng.random(total) < 0.04) & (vis_idx > 0)
    impossible = rng.random(total) < 0.005
    actual = np.where(impossible, consent - rng.integers(1, 30, total).astype("timedelta64[D]"), actual)
    actual = actual.astype("datetime64[D]")
    actual[missed] = np.datetime64("NaT")

    df = pd.DataFrame({
        "visit_id": np.arange(1, total + 1),
        "subject_id": subjects["subject_id"].values[subj_idx],
        "visit_name": names[vis_idx],
        "scheduled_date": scheduled.astype("datetime64[D]"),
        "actual_date": actual,
        "visit_status": np.where(missed, "MISSED", "COMPLETED"),
    })
    dup = df.iloc[rng.choice(total, int(total * 0.005), replace=False)].copy()
    dup["visit_id"] = np.arange(total + 1, total + 1 + len(dup))
    return pd.concat([df, dup], ignore_index=True), subj_idx, vis_idx, bad


def build_ae(rng, subjects, visits, subj_idx, bad):
    base = visits.iloc[: len(subj_idx)]
    arm = subjects["arm"].values[subj_idx]
    p = np.where(arm == "TREATMENT", 0.16, 0.11)
    pick = (rng.random(len(base)) < p) & (base["visit_status"].values == "COMPLETED") \
        & base["actual_date"].notna().values
    sel = np.where(pick)[0]
    m = len(sel)
    serious = rng.random(m) < 0.02
    severity = rng.choice(["MILD", "MODERATE", "SEVERE"], m, p=[0.62, 0.30, 0.08])
    severity[serious] = "SEVERE"
    lag = np.where(serious, rng.poisson(0.7, m), rng.poisson(3, m)) + np.where(bad[sel], 5, 0)
    onset = base["actual_date"].values[sel] + rng.integers(0, 15, m).astype("timedelta64[D]")
    return pd.DataFrame({
        "ae_id": np.arange(1, m + 1),
        "subject_id": base["subject_id"].values[sel],
        "visit_id": base["visit_id"].values[sel],
        "ae_term": rng.choice(AE_TERMS, m),
        "severity": severity,
        "is_serious": serious,
        "onset_date": onset.astype("datetime64[D]"),
        "reported_date": (onset + lag.astype("timedelta64[D]")).astype("datetime64[D]"),
    })


KPI_MD = """# Clinical Trial Operations KPI Definitions (synthetic)

## Screen Failure Rate
Subjects with subject_status = 'SCREEN_FAILED' divided by all subjects consented,
by study and site.

## Dropout (Discontinuation) Rate
Subjects with subject_status = 'DISCONTINUED' divided by subjects who passed
screening. A site with an unusually high rate needs review.

## Visit Compliance
Completed visits whose actual_date is within +/-3 days of scheduled_date, divided
by all scheduled visits. Missed visits count as non-compliant.

## Missed Visit Rate
visit_status = 'MISSED' divided by all scheduled visits.

## Adverse Event (AE) Rate
Adverse events per 100 completed visits, by arm and study. Compare TREATMENT vs
PLACEBO for safety signals.

## Serious AE Reporting Timeliness
For is_serious = true, days between onset_date and reported_date. Expected
reporting within 1 day; longer is a compliance concern.

## Data Quality Rules
- actual_date must not be before the subject's consent_date.
- no duplicate (subject_id, visit_name) pairs.
- age should be present for all enrolled subjects.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=170_000)
    ap.add_argument("--out", default="pharma_data")
    a = ap.parse_args()
    rng = np.random.default_rng(SEED)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    studies, sites = build_studies(rng), build_sites(rng)
    subjects, site_idx = build_subjects(rng, a.subjects, studies, sites)
    visits, subj_idx, _, bad = build_visits(rng, subjects, site_idx)
    ae = build_ae(rng, subjects, visits, subj_idx, bad)

    tables = {"studies": studies, "trial_sites": sites, "subjects": subjects,
              "visits": visits, "adverse_events": ae}
    total = 0
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False)
        total += len(df)
        print(f"{name:<16}{len(df):>10,}")
    (out / "kpi_definitions.md").write_text(KPI_MD)
    print(f"{'total rows':<16}{total:>10,}\nwritten to: {out.resolve()}")


if __name__ == "__main__":
    main()