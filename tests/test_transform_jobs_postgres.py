import os
from datetime import datetime

import psycopg
import pytest

from pipeline import transform_jobs


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


def test_process_raw_jobs_converts_valid_timestamp_to_utc(db_cursor):
    # Use a non-UTC session timezone to prove conversion is explicitly UTC.
    db_cursor.execute("SET LOCAL TIME ZONE 'America/Vancouver';")

    db_cursor.execute(
        """
        INSERT INTO raw_jobs (
            source,
            source_job_id,
            company_name,
            title,
            posted_at_raw,
            raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, '{}'::jsonb);
        """,
        (
            "arbeitnow",
            "postgres-valid-timestamp",
            "Example Company",
            "Data Engineer",
            "946684800",
        ),
    )

    counts = transform_jobs.process_raw_jobs(db_cursor)

    assert counts == {
        "fetched": 1,
        "inserted": 1,
        "duplicates_skipped": 0,
        "invalid_skipped": 0,
        "invalid_timestamps": 0,
    }

    db_cursor.execute(
        """
        SELECT posted_at
        FROM jobs_cleaned
        WHERE source_job_id = %s;
        """,
        ("postgres-valid-timestamp",),
    )

    posted_at = db_cursor.fetchone()[0]

    assert posted_at == datetime(2000, 1, 1, 0, 0, 0)


def test_process_raw_jobs_accepts_missing_timestamp(db_cursor):
    db_cursor.execute(
        """
        INSERT INTO raw_jobs (
            source,
            source_job_id,
            company_name,
            title,
            posted_at_raw,
            raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, '{}'::jsonb);
        """,
        (
            "arbeitnow",
            "postgres-missing-timestamp",
            "Example Company",
            "Backend Developer",
            None,
        ),
    )

    counts = transform_jobs.process_raw_jobs(db_cursor)

    assert counts == {
        "fetched": 1,
        "inserted": 1,
        "duplicates_skipped": 0,
        "invalid_skipped": 0,
        "invalid_timestamps": 0,
    }

    db_cursor.execute(
        """
        SELECT posted_at
        FROM jobs_cleaned
        WHERE source_job_id = %s;
        """,
        ("postgres-missing-timestamp",),
    )

    posted_at = db_cursor.fetchone()[0]

    assert posted_at is None


def test_process_raw_jobs_replaces_malformed_timestamp_with_null(db_cursor):
    db_cursor.execute(
        """
        INSERT INTO raw_jobs (
            source,
            source_job_id,
            company_name,
            title,
            posted_at_raw,
            raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, '{}'::jsonb);
        """,
        (
            "arbeitnow",
            "postgres-malformed-timestamp",
            "Example Company",
            "Data Analyst",
            "not-a-timestamp",
        ),
    )

    counts = transform_jobs.process_raw_jobs(db_cursor)

    assert counts == {
        "fetched": 1,
        "inserted": 1,
        "duplicates_skipped": 0,
        "invalid_skipped": 0,
        "invalid_timestamps": 1,
    }

    db_cursor.execute(
        """
        SELECT posted_at
        FROM jobs_cleaned
        WHERE source_job_id = %s;
        """,
        ("postgres-malformed-timestamp",),
    )

    posted_at = db_cursor.fetchone()[0]

    assert posted_at is None


def test_process_raw_jobs_replaces_millisecond_timestamp_with_null(db_cursor):
    db_cursor.execute(
        """
        INSERT INTO raw_jobs (
            source,
            source_job_id,
            company_name,
            title,
            posted_at_raw,
            raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, '{}'::jsonb);
        """,
        (
            "arbeitnow",
            "postgres-millisecond-timestamp",
            "Example Company",
            "Data Engineer",
            "1710000000000",
        ),
    )

    counts = transform_jobs.process_raw_jobs(db_cursor)

    assert counts == {
        "fetched": 1,
        "inserted": 1,
        "duplicates_skipped": 0,
        "invalid_skipped": 0,
        "invalid_timestamps": 1,
    }

    db_cursor.execute(
        """
        SELECT posted_at
        FROM jobs_cleaned
        WHERE source_job_id = %s;
        """,
        ("postgres-millisecond-timestamp",),
    )

    posted_at = db_cursor.fetchone()[0]

    assert posted_at is None


def test_process_raw_jobs_skips_blank_required_field(db_cursor):
    db_cursor.execute(
        """
        INSERT INTO raw_jobs (
            source,
            source_job_id,
            company_name,
            title,
            posted_at_raw,
            raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, '{}'::jsonb);
        """,
        (
            "arbeitnow",
            "postgres-blank-company",
            "   ",
            "Backend Developer",
            "1710000000",
        ),
    )

    counts = transform_jobs.process_raw_jobs(db_cursor)

    assert counts == {
        "fetched": 1,
        "inserted": 0,
        "duplicates_skipped": 0,
        "invalid_skipped": 1,
        "invalid_timestamps": 0,
    }

    db_cursor.execute(
        """
        SELECT COUNT(*)
        FROM jobs_cleaned
        WHERE source_job_id = %s;
        """,
        ("postgres-blank-company",),
    )

    cleaned_count = db_cursor.fetchone()[0]

    assert cleaned_count == 0


def test_process_raw_jobs_skips_existing_cleaned_job(db_cursor):
    db_cursor.execute(
        """
        INSERT INTO raw_jobs (
            source,
            source_job_id,
            company_name,
            title,
            posted_at_raw,
            raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, '{}'::jsonb)
        RETURNING id;
        """,
        (
            "arbeitnow",
            "postgres-existing-job",
            "Example Company",
            "Data Engineer",
            "1710000000",
        ),
    )

    raw_job_id = db_cursor.fetchone()[0]

    # Simulate a job that was already transformed earlier
    db_cursor.execute(
        """
        INSERT INTO jobs_cleaned (
            raw_job_id,
            source,
            source_job_id,
            company_name,
            title
        )
        VALUES (%s, %s, %s, %s, %s);
        """,
        (
            raw_job_id,
            "arbeitnow",
            "postgres-existing-job",
            "Example Company",
            "Data Engineer",
        ),
    )

    counts = transform_jobs.process_raw_jobs(db_cursor)

    assert counts == {
        "fetched": 1,
        "inserted": 0,
        "duplicates_skipped": 1,
        "invalid_skipped": 0,
        "invalid_timestamps": 0,
    }

    db_cursor.execute(
        """
        SELECT COUNT(*)
        FROM jobs_cleaned
        WHERE source_job_id = %s;
        """,
        ("postgres-existing-job",),
    )

    cleaned_count = db_cursor.fetchone()[0]

    assert cleaned_count == 1
