from datetime import datetime

import pytest

from pipeline import transform_jobs


@pytest.mark.parametrize(
    "raw_timestamp, expected_timestamp, invalid_timestamps",
    [
        ("946684800", datetime(2000, 1, 1), 0),
        (None, None, 0),
        ("not-a-timestamp", None, 1),
        ("1710000000000", None, 1),
    ],
    ids=["valid-utc", "missing", "malformed", "milliseconds"],
)
def test_process_raw_jobs_normalizes_timestamps(
    db_cursor, raw_timestamp, expected_timestamp, invalid_timestamps
):
    # A non-UTC session should not change the stored UTC value
    db_cursor.execute("SET LOCAL TIME ZONE 'America/Vancouver';")

    db_cursor.execute(
        """
        INSERT INTO raw_jobs (
            source, source_job_id, company_name, title, posted_at_raw, raw_payload
        )
        VALUES ('arbeitnow', 'timestamp-job', 'Example Company',
                'Data Engineer', %s, '{}'::jsonb);
        """,
        (raw_timestamp,),
    )

    counts = transform_jobs.process_raw_jobs(db_cursor)

    assert counts == {
        "fetched": 1,
        "inserted": 1,
        "duplicates_skipped": 0,
        "invalid_skipped": 0,
        "invalid_timestamps": invalid_timestamps,
    }

    db_cursor.execute("SELECT posted_at FROM jobs_cleaned;")
    assert db_cursor.fetchone()[0] == expected_timestamp


def test_process_raw_jobs_skips_blank_required_field(db_cursor):

    db_cursor.execute("""
        INSERT INTO raw_jobs (
            source, source_job_id, company_name, title, posted_at_raw, raw_payload
        )
        VALUES ('arbeitnow', 'blank-company', '   ',
                'Backend Developer', '1710000000', '{}'::jsonb);
        """)

    counts = transform_jobs.process_raw_jobs(db_cursor)

    assert counts == {
        "fetched": 1,
        "inserted": 0,
        "duplicates_skipped": 0,
        "invalid_skipped": 1,
        "invalid_timestamps": 0,
    }

    db_cursor.execute("SELECT COUNT(*) FROM jobs_cleaned;")
    assert db_cursor.fetchone()[0] == 0


def test_process_raw_jobs_skips_existing_cleaned_job(db_cursor):

    db_cursor.execute("""
        INSERT INTO raw_jobs (
            source, source_job_id, company_name, title, posted_at_raw, raw_payload
        )
        VALUES ('arbeitnow', 'existing-job', 'Example Company',
                'Data Engineer', '1710000000', '{}'::jsonb);
        """)

    # Process the same raw job twice to verify reruns do not create duplicates
    first_counts = transform_jobs.process_raw_jobs(db_cursor)
    counts = transform_jobs.process_raw_jobs(db_cursor)

    assert first_counts["inserted"] == 1

    assert counts == {
        "fetched": 1,
        "inserted": 0,
        "duplicates_skipped": 1,
        "invalid_skipped": 0,
        "invalid_timestamps": 0,
    }

    db_cursor.execute("SELECT COUNT(*) FROM jobs_cleaned;")
    assert db_cursor.fetchone()[0] == 1
