"""part 1: try to predict subject dropout, and evaluate the result honestly.

Run from the project root with:  python -m analytics.dropout_model

The question: using only information available EARLY (by the baseline visit),
can we predict which subjects will later discontinue the study?

The main lessons of this script are about METHOD:
  - choose the population and the label carefully
  - avoid data leakage (never use information from the future)
  - always compare against a dumb baseline
  - report the result honestly, even when it is disappointing
"""
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from analytics.db import get_engine

engine = get_engine()
RANDOM_STATE = 42  # fixed seed so every run gives the same split and results

# =============================================================================
# 1. POPULATION: who do we train on?
# =============================================================================
# We only keep subjects whose outcome is KNOWN:
#   COMPLETED     -> did not drop out
#   DISCONTINUED  -> dropped out
# We exclude SCREEN_FAILED (never started the study) and ENROLLED (still ongoing,
# so we do not know yet how their story ends).
subjects = pd.read_sql(
    """
    SELECT s.subject_id, s.age, s.sex, s.arm, s.subject_status,
           st.phase, st.therapeutic_area, t.region
    FROM subjects s
    JOIN studies st     ON st.study_id = s.study_id
    JOIN trial_sites t  ON t.site_id   = s.site_id
    WHERE s.subject_status IN ('COMPLETED', 'DISCONTINUED')
    """,
    engine,
)

# =============================================================================
# 2. EARLY-VISIT FEATURES (from the CLEAN view, first two visits only)
# =============================================================================
# This uses "conditional aggregation": MAX(CASE WHEN ... THEN ... END) turns
# rows into columns (a pivot), giving one row per subject.
# LEAKAGE WARNING: we deliberately look ONLY at SCREENING and BASELINE.
# Total number of visits would be a terrible feature: dropouts have fewer visits
# BECAUSE they dropped out, so it would reveal the answer from the future.
early = pd.read_sql(
    """
    SELECT subject_id,
           MAX(CASE WHEN visit_name = 'SCREENING' THEN actual_date - scheduled_date END) AS screening_days_late,
           MAX(CASE WHEN visit_name = 'BASELINE'  THEN actual_date - scheduled_date END) AS baseline_days_late,
           BOOL_OR(visit_name = 'BASELINE' AND visit_status = 'MISSED')::int             AS baseline_missed
    FROM visits_clean
    WHERE visit_name IN ('SCREENING', 'BASELINE')
    GROUP BY subject_id
    """,
    engine,
)

# Join the two together: one row per subject, with features and the outcome.
df = subjects.merge(early, on="subject_id", how="left")
df["age"] = pd.to_numeric(df["age"])                         # NUMERIC arrives as Decimal
df["dropped"] = (df["subject_status"] == "DISCONTINUED").astype(int)  # the label: 1 = dropped out

prevalence = df["dropped"].mean()
print(f"subjects used: {len(df):,}   dropout prevalence: {prevalence:.1%}\n")

# =============================================================================
# 3. FEATURES, SPLIT, AND PREPROCESSING
# =============================================================================
numeric = ["age", "screening_days_late", "baseline_days_late", "baseline_missed"]
categorical = ["sex", "arm", "phase", "therapeutic_area", "region"]

X = df[numeric + categorical]   # inputs the model may look at
y = df["dropped"]               # what we want to predict

# Hold back 20% of subjects that the model never sees during training.
# stratify=y keeps the same dropout percentage in both halves.
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
)

# Preprocessing is wrapped in a Pipeline so it is learned ONLY from training data
# (learning it from all the data would leak information from the test set).
numeric_steps = Pipeline([
    ("fill_missing", SimpleImputer(strategy="median", add_indicator=True)),  # fill gaps with the median + flag which were missing
    ("scale", StandardScaler()),                                             # put numbers on a comparable scale
])
prep = ColumnTransformer(
    [
        ("num", numeric_steps, numeric),
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),  # text categories -> 0/1 columns
    ],
    sparse_threshold=0,  # always return a normal dense array (gradient boosting needs that)
)

# =============================================================================
# 4. TRAIN AND COMPARE MODELS (always include a dumb baseline)
# =============================================================================
models = {
    "baseline (always the average)": DummyClassifier(strategy="prior"),
    "logistic regression": LogisticRegression(max_iter=1000),
    "gradient boosting": HistGradientBoostingClassifier(random_state=RANDOM_STATE),
}

print(f"{'model':<32}{'ROC AUC':>9}{'PR AUC':>9}")
best_auc = 0.0
for name, clf in models.items():
    pipe = Pipeline([("prep", prep), ("model", clf)])
    pipe.fit(X_train, y_train)                       # learn from the training subjects only
    prob = pipe.predict_proba(X_test)[:, 1]          # predicted probability of dropping out
    auc = roc_auc_score(y_test, prob)                # 0.5 = coin flip, 1.0 = perfect
    pr = average_precision_score(y_test, prob)       # compare against prevalence, not 0.5
    print(f"{name:<32}{auc:>9.3f}{pr:>9.3f}")
    if not name.startswith("baseline"):
        best_auc = max(best_auc, auc)

print(f"\n(PR AUC of a useless model is about the prevalence: {prevalence:.3f})")

# =============================================================================
# 5. HONEST CONCLUSION
# =============================================================================
if best_auc < 0.55:
    print(
        "\nConclusion: the models are barely better than a coin flip. On this data,\n"
        "early subject-level features do not predict dropout, so we would NOT ship\n"
        "this model. In the generator, dropout depends only on WHICH SITE a subject\n"
        "is at, and the two problem sites hold well under 1% of subjects. The real\n"
        "signal lives at the site level, which is what site_risk.py explores."
    )
else:
    print("\nConclusion: the models beat the baseline, so inspect them for leakage before trusting them.")