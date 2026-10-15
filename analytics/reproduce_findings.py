"""Day 4: reproduce the Day 3 SQL findings in Pandas and chart the outlier sites."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to files, no pop-up window
import matplotlib.pyplot as plt
import pandas as pd

from analytics.db import get_engine

engine = get_engine()
Path("charts").mkdir(exist_ok=True)

# ---------------------------------------------------------------- load
visits = pd.read_sql("SELECT * FROM visits", engine,
                     parse_dates=["scheduled_date", "actual_date"])
subjects = pd.read_sql("SELECT * FROM subjects", engine,
                       parse_dates=["consent_date"])
ae = pd.read_sql("SELECT * FROM adverse_events", engine,
                 parse_dates=["onset_date", "reported_date"])
subjects["age"] = pd.to_numeric(subjects["age"])  # NUMERIC arrives as Decimal
print(f"loaded: visits={len(visits):,} subjects={len(subjects):,} ae={len(ae):,}\n")

# ---------------------------------------------------------------- profiling
visits = visits.sort_values("visit_id")
dup = visits.duplicated(subset=["subject_id", "visit_name"], keep="first")
print(f"duplicate visit rows:        {dup.sum():,}")        # expect 5,264

v = visits.merge(subjects[["subject_id", "site_id", "consent_date"]],
                 on="subject_id", how="left")
before = (v["actual_date"] < v["consent_date"]).sum()
print(f"visits before consent:       {before:,}")           # expect 5,259
print(f"missing ages:                {subjects['age'].isna().sum():,}")  # 1,684
missed = (visits["visit_status"] == "MISSED").mean() * 100
print(f"missed visit rate:           {missed:.2f}%\n")       # 3.36%

# ---------------------------------------------------------------- clean (same rules as the SQL view)
v["rn"] = v.groupby(["subject_id", "visit_name"]).cumcount() + 1
clean = v[(v["rn"] == 1) & (v["actual_date"].isna() | (v["actual_date"] >= v["consent_date"]))]
print(f"clean visits:                {len(clean):,}\n")      # expect 1,047,619

# ---------------------------------------------------------------- site metrics
done = clean[clean["visit_status"] == "COMPLETED"].copy()
done["days_late"] = (done["actual_date"] - done["scheduled_date"]).dt.days
late = (done.groupby("site_id")
            .agg(visits=("days_late", "size"), avg=("days_late", "mean"))
            .query("visits >= 200")["avg"].sort_values(ascending=False))

dropout = (subjects.assign(dropped=subjects["subject_status"].eq("DISCONTINUED"))
                   .groupby("site_id")
                   .agg(n=("dropped", "size"), pct=("dropped", "mean"))
                   .query("n >= 50"))
dropout = (dropout["pct"] * 100).sort_values(ascending=False)

ae = ae.merge(subjects[["subject_id", "site_id"]], on="subject_id")
ae["lag"] = (ae["reported_date"] - ae["onset_date"]).dt.days
ae_lag = (ae.groupby("site_id")
            .agg(n=("lag", "size"), avg=("lag", "mean"))
            .query("n >= 30")["avg"].sort_values(ascending=False))

for name, s in [("Avg days late", late), ("Dropout %", dropout), ("AE report lag", ae_lag)]:
    print(f"{name} - top 3:\n{s.head(3).round(2).to_string()}\n")

# ---------------------------------------------------------------- chart
def bar(ax, series, title, xlabel):
    top = series.head(10).iloc[::-1]  # biggest at the top of the chart
    colors = ["#c0392b" if i >= len(top) - 2 else "#7f8c8d" for i in range(len(top))]
    ax.barh(top.index, top.values, color=colors)
    ax.set_title(title)
    ax.set_xlabel(xlabel)

fig, axes = plt.subplots(1, 3, figsize=(16, 5))
bar(axes[0], dropout, "Dropout rate", "% of subjects discontinued")
bar(axes[1], late, "Visit lateness", "average days late")
bar(axes[2], ae_lag, "Adverse event reporting lag", "average days to report")
fig.suptitle("Two sites stand out on all three measures (synthetic data)")
fig.tight_layout()
fig.savefig("charts/site_outliers.png", dpi=130)
print("saved charts/site_outliers.png")