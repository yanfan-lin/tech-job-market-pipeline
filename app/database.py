"""Create PostgreSQL database connection for the application"""

import psycopg

from app.config import get_required_env


def get_db_connection():
    """Open a PostgreSQL connection; callers own transaction handling and cleanup."""

    return psycopg.connect(get_required_env("DATABASE_URL"))
