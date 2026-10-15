"""Part 2: score every site for operational risk (unsupervised anomaly detection).

Run from the project root with:  python -m analytics.site_risk

Part 1 showed the signal is at the SITE level, not the subject level.
Here we build one row of metrics per site and ask: which sites look unlike the others?
We use two methods and compare them:
  1. a robust z-score composite  (simple and explainable)
  2. an Isolation Forest         (a machine-learning anomaly detector)
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to a file, no pop-up window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from analytics.db import get_engine

engine = get_engine()
Path("charts").mkdir(exist_ok=True)

# =============================================================================
# 1. ONE ROW PER SITE, aggregated INSIDE the database
# =============================================================================
# Doing the heavy aggregation in SQL means Python only receives ~800 rows,
# instead of pulling over a million raw rows into memory.
# Each CTE (WITH ... AS) computes one family of metrics; USING (site_id) joins them.
sites = pd.read_sql(
    """
    WITH subj AS (
        SELECT site_id,
               COUNT(*) AS subjects,
               AVG((subject_status = 'DISCONTINUED')::int) AS dropout_rate
        FROM subjects
        GROUP BY site_id
    ),
    vis AS (
        SELECT s.site_id,
               AVG(v.actual_date - v.scheduled_date) FILTER (WHERE v.visit_status = 'COMPLETED') AS avg_days_late,
               AVG((v.visit_status = 'MISSED')::int) AS missed_rate
        FROM visits_clean v
        JOIN subjects s ON s.subject_id = v.subject_id
        GROUP BY s.site_id
    ),
    aes AS (
        SELECT s.site_id,
               AVG(a.reported_date - a.onset_date) AS ae_report_lag
        FROM adverse_events a
        JOIN subjects s ON s.subject_id = a.subject_id
        GROUP BY s.site_id
    )
    SELECT site_id, subjects, dropout_rate, avg_days_late, missed_rate, ae_report_lag
    FROM subj
    JOIN vis USING (site_id)
    LEFT JOIN aes USING (site_id)
    WHERE subj.subjects >= 50
    """,
    engine,
).set_index("site_id")

# AVG() in Postgres returns Decimal numbers; convert every column to plain floats.
sites = sites.apply(pd.to_numeric)
sites["ae_report_lag"] = sites["ae_report_lag"].fillna(sites["ae_report_lag"].median())
print(f"sites scored: {len(sites)}\n")

FEATURES = ["dropout_rate", "avg_days_late", "missed_rate", "ae_report_lag"]

# =============================================================================
# 2. METHOD A: robust z-score composite
# =============================================================================
# A z-score says "how many typical-spreads away from normal is this site?".
# "Robust" means we use the MEDIAN and MAD (median absolute deviation) instead of
# mean and standard deviation, so the outliers we are hunting cannot distort
# the definition of "normal". The 1.4826 factor makes MAD comparable to a std dev.
def robust_z(col: pd.Series) -> pd.Series:
    mad = (col - col.median()).abs().median()
    return (col - col.median()) / (1.4826 * mad)

z = sites[FEATURES].apply(robust_z)
# Average the z-scores. Only HIGH values are risky for all four metrics,
# so we clip negatives to 0 (a site that is unusually good is not a risk).
sites["z_risk"] = z.clip(lower=0).mean(axis=1)

# =============================================================================
# 3. METHOD B: Isolation Forest
# =============================================================================
# Isolation Forest builds many random decision trees. Points that are unusual get
# isolated from the rest in very few splits, so they receive a high anomaly score.
scaled = StandardScaler().fit_transform(sites[FEATURES])
iso = IsolationForest(n_estimators=300, random_state=42).fit(scaled)
sites["iso_risk"] = -iso.score_samples(scaled)  # flip the sign so bigger = more unusual

# =============================================================================
# 4. COMPARE THE METHODS AND CHECK THEM AGAINST KNOWN TRUTH
# =============================================================================
print("Top 5 by robust z-score composite:")
print(sites.sort_values("z_risk", ascending=False).head(5)[FEATURES + ["z_risk"]].round(3).to_string(), "\n")
print("Top 5 by Isolation Forest:")
print(sites.sort_values("iso_risk", ascending=False).head(5)[FEATURES + ["iso_risk"]].round(3).to_string(), "\n")

# Because WE planted two problem sites in the generator, we can measure how well
# each method finds them. (In real life you rarely have this ground truth.)
PLANTED = {"SITE0034", "SITE0412"}
for col in ["z_risk", "iso_risk"]:
    top2 = set(sites.sort_values(col, ascending=False).head(2).index)
    print(f"{col}: planted sites found in top 2 = {len(top2 & PLANTED)} of 2")

# =============================================================================
# 5. CHART
# =============================================================================
fig, ax = plt.subplots(figsize=(9, 6))
pts = ax.scatter(sites["dropout_rate"] * 100, sites["avg_days_late"],
                 c=sites["z_risk"], cmap="viridis_r", s=18, alpha=0.8)
for site in sites.sort_values("z_risk", ascending=False).head(5).index:
    ax.annotate(site, (sites.loc[site, "dropout_rate"] * 100, sites.loc[site, "avg_days_late"]),
                textcoords="offset points", xytext=(6, 4), fontsize=9)
ax.set_xlabel("dropout rate (%)")
ax.set_ylabel("average days late")
ax.set_title("Site risk: each dot is one site (synthetic data)")
fig.colorbar(pts, label="risk score (robust z)")
fig.tight_layout()
fig.savefig("charts/site_risk.png", dpi=130)
print("\nsaved charts/site_risk.png")