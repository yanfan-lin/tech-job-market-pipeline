import os

import psycopg
import pytest

from pipeline import skill_extractor


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


def insert_cleaned_job(cur, source_job_id, title, description):
    """Insert one raw and cleaned job and return the cleaned job ID."""

    cur.execute(
        """
        INSERT INTO raw_jobs (
            source,
            source_job_id,
            company_name,
            title,
            description,
            raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, '{}'::jsonb)
        RETURNING id;
        """,
        (
            "arbeitnow",
            source_job_id,
            "Example Company",
            title,
            description,
        ),
    )

    raw_job_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO jobs_cleaned (
            raw_job_id,
            source,
            source_job_id,
            company_name,
            title,
            description
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
        """,
        (
            raw_job_id,
            "arbeitnow",
            source_job_id,
            "Example Company",
            title,
            description,
        ),
    )

    return cur.fetchone()[0]


def test_process_cleaned_jobs_inserts_real_skills_and_mappings(db_cursor):
    insert_cleaned_job(
        db_cursor,
        "postgres-python-job",
        "Python Engineer",
        "Build SQL pipelines with Docker.",
    )

    insert_cleaned_job(
        db_cursor,
        "postgres-marketing-job",
        "JavaScript Developer",
        "Create digital marketing tools.",
    )

    counts = skill_extractor.process_cleaned_jobs(db_cursor)

    assert counts == {
        "jobs_processed": 2,
        "jobs_with_matches": 1,
        "skills_inserted": 3,
        "mappings_inserted": 3,
        "mappings_skipped": 0,
    }

    db_cursor.execute("""
        SELECT skill_name
        FROM skills_extracted
        ORDER BY skill_name;
        """)

    skill_names = [row[0] for row in db_cursor.fetchall()]

    assert skill_names == [
        "Docker",
        "Python",
        "SQL",
    ]

    db_cursor.execute("SELECT COUNT(*) FROM job_skill_map;")
    mapping_count = db_cursor.fetchone()[0]

    assert mapping_count == 3


def test_process_cleaned_jobs_does_not_duplicate_existing_mappings(db_cursor):
    insert_cleaned_job(
        db_cursor,
        "postgres-rerun-job",
        "Python Engineer",
        "Build SQL pipelines with Docker.",
    )

    first_counts = skill_extractor.process_cleaned_jobs(db_cursor)
    second_counts = skill_extractor.process_cleaned_jobs(db_cursor)

    assert first_counts == {
        "jobs_processed": 1,
        "jobs_with_matches": 1,
        "skills_inserted": 3,
        "mappings_inserted": 3,
        "mappings_skipped": 0,
    }

    assert second_counts == {
        "jobs_processed": 1,
        "jobs_with_matches": 1,
        "skills_inserted": 0,
        "mappings_inserted": 0,
        "mappings_skipped": 3,
    }

    db_cursor.execute("SELECT COUNT(*) FROM skills_extracted;")
    skill_count = db_cursor.fetchone()[0]

    db_cursor.execute("SELECT COUNT(*) FROM job_skill_map;")
    mapping_count = db_cursor.fetchone()[0]

    assert skill_count == 3
    assert mapping_count == 3
