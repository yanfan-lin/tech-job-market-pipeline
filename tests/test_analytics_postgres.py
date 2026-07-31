"""Verify analytics queries against the dedicated PostgreSQL test database."""

import os

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def analytics_database():
    """Provide a clean and reusable PostgreSQL analytics test database."""

    test_database_url = os.getenv("TEST_DATABASE_URL")

    if not test_database_url:
        pytest.skip("TEST_DATABASE_URL is not set")

    conn = psycopg.connect(test_database_url)
    cur = conn.cursor()

    cur.execute("SELECT current_database();")
    database_name = cur.fetchone()[0]

    # Stop if using the normal project database
    if database_name != "tech_jobs_test":
        cur.close()
        conn.close()
        pytest.fail("Integration tests must use tech_jobs_test")

    # Start with empty tables visible to the endpoint's separate connection
    cur.execute("""
        TRUNCATE TABLE
            job_skill_map,
            skills_extracted,
            jobs_cleaned,
            raw_jobs
        RESTART IDENTITY CASCADE;
        """)
    conn.commit()

    try:
        yield conn, cur, test_database_url

    finally:
        # Remove committed test data after the endpoint request finishes
        cur.execute("""
            TRUNCATE TABLE
                job_skill_map,
                skills_extracted,
                jobs_cleaned,
                raw_jobs
            RESTART IDENTITY CASCADE;
            """)
        conn.commit()

        cur.close()
        conn.close()


def insert_cleaned_job(
    cur,
    source_job_id: str,
    title: str,
    remote: bool | None,
) -> int:
    """Insert matching raw and cleaned records and return the cleaned job ID."""

    cur.execute(
        """
        INSERT INTO raw_jobs (
            source,
            source_job_id,
            company_name,
            title,
            raw_payload
        )
        VALUES (%s, %s, %s, %s, '{}'::jsonb)
        RETURNING id;
        """,
        (
            "arbeitnow",
            source_job_id,
            "Example Company",
            title,
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
            remote
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
            remote,
        ),
    )

    return cur.fetchone()[0]


def test_analytics_endpoints_use_real_postgresql_aggregation(
    analytics_database,
    monkeypatch,
):
    """Verify analytics endpoints execute their real PostgreSQL queries."""

    conn, cur, test_database_url = analytics_database

    first_job_id = insert_cleaned_job(
        cur,
        "analytics-python-sql",
        "Data Engineer",
        True,
    )
    second_job_id = insert_cleaned_job(
        cur,
        "analytics-python",
        "Backend Developer",
        False,
    )

    cur.execute(
        """
        INSERT INTO skills_extracted (skill_name)
        VALUES (%s), (%s)
        RETURNING id, skill_name;
        """,
        (
            "Python",
            "SQL",
        ),
    )

    # Map each skill name to its generated database ID for job-skill inserts
    skill_ids = {skill_name: skill_id for skill_id, skill_name in cur.fetchall()}

    cur.execute(
        """
        INSERT INTO job_skill_map (job_id, skill_id)
        VALUES
            (%s, %s),
            (%s, %s),
            (%s, %s);
        """,
        (
            first_job_id,
            skill_ids["Python"],
            first_job_id,
            skill_ids["SQL"],
            second_job_id,
            skill_ids["Python"],
        ),
    )

    # Commit the seed data so the endpoint's separate connection can see it
    conn.commit()

    # Direct application connections to the dedicated database for this test
    monkeypatch.setenv("DATABASE_URL", test_database_url)

    skills_response = client.get("/analytics/top-skills")

    assert skills_response.status_code == 200
    assert skills_response.json() == [
        {
            "skill_name": "Python",
            "job_count": 2,
        },
        {
            "skill_name": "SQL",
            "job_count": 1,
        },
    ]

    titles_response = client.get("/analytics/top-titles")

    assert titles_response.status_code == 200
    assert titles_response.json() == [
        {
            "title": "Backend Developer",
            "job_count": 1,
        },
        {
            "title": "Data Engineer",
            "job_count": 1,
        },
    ]

    remote_response = client.get("/analytics/remote-status")

    assert remote_response.status_code == 200
    assert remote_response.json() == [
        {
            "remote": True,
            "job_count": 1,
        },
        {
            "remote": False,
            "job_count": 1,
        },
    ]
