import os

import psycopg
import pytest


@pytest.fixture
def db_cursor():
    """Provide an isolated cursor connected only to the test database."""

    test_database_url = os.getenv("TEST_DATABASE_URL")

    if not test_database_url:
        pytest.skip("TEST_DATABASE_URL is not set")

    conn = psycopg.connect(test_database_url)
    cur = conn.cursor()

    cur.execute("SELECT current_database();")
    database_name = cur.fetchone()[0]

    # Only use the test database
    if database_name != "tech_jobs_test":
        cur.close()
        conn.close()
        pytest.fail("Integration tests must use tech_jobs_test")

    # Start every test with empty tables inside the current transaction.
    cur.execute("""
        TRUNCATE TABLE
            job_skill_map,
            skills_extracted,
            jobs_cleaned,
            raw_jobs
        RESTART IDENTITY CASCADE;
        """)

    try:
        yield cur

    finally:
        # Remove every database change made by the test
        conn.rollback()
        cur.close()
        conn.close()
