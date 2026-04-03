# For python to connect to PostgreSQL
import psycopg

# Import project settings from config
from app.config import settings


def get_db_connection():
    # Return a new PostgreSQL connection using DATABASE_URL
    return psycopg.connect(settings.DATABASE_URL)
