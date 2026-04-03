# For python to connect to PostgreSQL
import psycopg

# Import project settings from config
from app.config import settings


def get_db_connection():
    # Return a new PostgreSQL connection using DATABASE_URL
    return psycopg.connect(settings.DATABASE_URL)


def test_db_connection():
    # open a database connection
    conn = get_db_connection()

    # create a cursor to test sql
    cur = conn.cursor()

    # Run a simple test query
    cur.execute("SELECT 123;")

    # Get result
    result = cur.fetchone()

    cur.close()
    conn.close()

    return result