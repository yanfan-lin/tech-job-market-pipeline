import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from pipeline import ingest_jobs


@pytest.fixture
def valid_job():
    """Provide one reusable valid Arbeitnow job record."""

    return {
        "slug": "data-engineer-123",
        "company_name": "Example Company",
        "title": "Data Engineer",
        "description": "<p>Build Python and SQL pipelines.</p>",
        "location": "Berlin",
        "remote": True,
        "url": "https://example.com/jobs/123",
        "created_at": 1_710_000_000,
        "tags": ["Python", "SQL"],
        "job_types": ["Full-time"],
    }


# Reject malformed API responses before processing jobs
@pytest.mark.parametrize(
    "raw_data, message",
    [
        (None, "API response must be a JSON object"),
        ([], "API response must be a JSON object"),
        ("invalid response", "API response must be a JSON object"),
        ({}, "API response must contain a 'data' field"),
        ({"data": None}, "API response 'data' field must be a list"),
        ({"data": {}}, "API response 'data' field must be a list"),
        ({"data": "not a list"}, "API response 'data' field must be a list"),
    ],
)
def test_extract_job_records_rejects_invalid_response(raw_data, message):
    with pytest.raises(ValueError, match=message):
        ingest_jobs.extract_job_records(raw_data)


def test_prepare_job_trims_required_fields_and_preserves_raw_payload(
    valid_job,
):
    job = valid_job.copy()
    job["slug"] = "   data-engineer-123    "
    job["company_name"] = "  Example Company  "
    job["title"] = "  Data Engineer  "

    prepared_job = ingest_jobs.prepare_job(job)

    # Clean mapped fields without changing the preserved source payload.
    assert prepared_job["source"] == "arbeitnow"
    assert prepared_job["source_job_id"] == "data-engineer-123"
    assert prepared_job["company_name"] == "Example Company"
    assert prepared_job["title"] == "Data Engineer"

    assert json.loads(prepared_job["raw_payload"]) == job


@pytest.mark.parametrize("field", ingest_jobs.REQUIRED_FIELDS)
def test_prepare_job_rejects_missing_required_field(valid_job, field):

    job = valid_job.copy()
    job.pop(field)

    assert ingest_jobs.prepare_job(job) is None


@pytest.mark.parametrize("field", ingest_jobs.REQUIRED_FIELDS)
@pytest.mark.parametrize(
    "invalid_value",
    [
        None,
        "",
        "   ",
        123,
    ],
)
def test_prepare_job_rejects_invalid_required_value(
    valid_job,
    field,
    invalid_value,
):
    job = valid_job.copy()
    job[field] = invalid_value

    assert ingest_jobs.prepare_job(job) is None


@pytest.mark.parametrize(
    "optional_fields, expected_json",
    [
        ({}, None),
        ({"tags": [], "job_types": []}, "[]"),
    ],
)
def test_prepare_job_preserves_missing_fields_and_empty_lists(
    optional_fields, expected_json
):
    job = {
        "slug": "backend-developer-123",
        "company_name": "Example Company",
        "title": "Backend Developer",
    }
    job.update(optional_fields)

    prepared_job = ingest_jobs.prepare_job(job)

    assert prepared_job["description"] is None
    assert prepared_job["location"] is None
    assert prepared_job["remote"] is None
    assert prepared_job["job_url"] is None
    assert prepared_job["posted_at_raw"] is None
    assert prepared_job["tags_raw"] == expected_json
    assert prepared_job["job_types_raw"] == expected_json


def test_process_jobs_counts_inserted_duplicate_and_invalid_records(
    valid_job,
):
    inserted_job = valid_job.copy()

    invalid_job = valid_job.copy()
    invalid_job["slug"] = "   "

    duplicate_job = valid_job.copy()
    duplicate_job["slug"] = "existing-job-456"

    cur = MagicMock()

    # Simulate one insert and one duplicate,
    # the invalid job never reaches SQL
    cur.fetchone.side_effect = [
        (101,),
        None,
    ]

    counts = ingest_jobs.process_jobs(
        cur,
        [
            inserted_job,
            invalid_job,
            duplicate_job,
        ],
    )

    assert counts == {
        "fetched": 3,
        "inserted": 1,
        "duplicates_skipped": 1,
        "invalid_skipped": 1,
    }

    # Invalid records should not be written
    assert cur.execute.call_count == 2

    # Keep duplicate protection and distinguish new inserts from conflicts
    sql = cur.execute.call_args.args[0]

    assert "ON CONFLICT (source_job_id) DO NOTHING" in sql
    assert "RETURNING id" in sql


def test_save_jobs_passes_failure_to_transaction_and_reraises(valid_job):

    conn = MagicMock()
    cur = MagicMock()

    conn.__enter__.return_value = conn
    conn.cursor.return_value = cur
    cur.__enter__.return_value = cur
    cur.execute.side_effect = RuntimeError("database write failed")

    with (
        patch.object(
            ingest_jobs,
            "get_db_connection",
            return_value=conn,
        ),
        pytest.raises(
            RuntimeError,
            match="database write failed",
        ),
    ):
        ingest_jobs.save_jobs([valid_job])

    # The write error should reach both contexts,
    # this mock does not test real rollback.
    cur.__exit__.assert_called_once()
    conn.__exit__.assert_called_once()

    assert conn.__exit__.call_args == cur.__exit__.call_args
    assert conn.__exit__.call_args.args[0] is RuntimeError


def test_main_logs_and_reraises_unexpected_failure(caplog):
    """Report ingestion failures without swallowing the exception."""

    with (
        patch.object(
            ingest_jobs,
            "get_jobs",
            side_effect=RuntimeError("API unavailable"),
        ),
        caplog.at_level(
            logging.ERROR,
            logger=ingest_jobs.logger.name,
        ),
        pytest.raises(
            RuntimeError,
            match="API unavailable",
        ),
    ):
        ingest_jobs.main()

    assert "Job ingestion failed." in caplog.messages
