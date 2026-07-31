"""Create PostgreSQL database connection for the application"""

import psycopg

from app.config import settings


def get_db_connection():
    """Open a PostgreSQL connection; callers own transaction handling and cleanup."""

    return psycopg.connect(settings.DATABASE_URL)
