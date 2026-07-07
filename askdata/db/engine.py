"""Creates SQLAlchemy engines for local BIRD databases."""

from sqlalchemy import create_engine


def CreateEngine(databaseUrl):
    """Creates a SQLAlchemy engine for the provided database URL."""
    return create_engine(databaseUrl)
