"""Create PostgreSQL database connection for the application"""

import psycopg

from app.config import settings


def get_db_connection():
    """Open and return a new PostgreSQL connection

    Caller must commit or rollback and close the connection.
    """

    return psycopg.connect(settings.DATABASE_URL)
