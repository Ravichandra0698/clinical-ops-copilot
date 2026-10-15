import os

from sqlalchemy import create_engine

DEFAULT_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/trials"


def get_engine():
    """One place that knows how to reach the database."""
    return create_engine(os.getenv("DATABASE_URL", DEFAULT_URL))