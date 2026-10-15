import pandas as pd

from analytics.db import get_engine

engine = get_engine()

counts = pd.read_sql(
    """
    SELECT 'subjects' AS table_name, COUNT(*) AS n FROM subjects
    UNION ALL SELECT 'visits', COUNT(*) FROM visits
    UNION ALL SELECT 'visits_clean', COUNT(*) FROM visits_clean
    """,
    engine,
)
print(counts, "\n")

visits = pd.read_sql(
    "SELECT * FROM visits_clean",
    engine,
    parse_dates=["scheduled_date", "actual_date"],
)
print("shape:", visits.shape, "\n")
print(visits.dtypes, "\n")
print(visits.head(), "\n")
print("memory MB:", round(visits.memory_usage(deep=True).sum() / 1e6, 1))