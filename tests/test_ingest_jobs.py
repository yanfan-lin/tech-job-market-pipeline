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


# ---
# API response validation tests
# ---
def test_extract_job_records_returns_job_list(valid_job):
    jobs = ingest_jobs.extract_job_records({"data": [valid_job]})

    assert jobs == [valid_job]


def test_extract_job_records_accepts_empty_list():
    jobs = ingest_jobs.extract_job_records({"data": []})

    assert jobs == []


@pytest.mark.parametrize(
    "raw_data",
    [
        None,
        [],
        "invalid response",
    ],
)
def test_extract_job_records_rejects_non_object_response(raw_data):
    with pytest.raises(
        ValueError,
        match="API response must be a JSON object",
    ):
        ingest_jobs.extract_job_records(raw_data)


def test_extract_job_records_rejects_missing_data_field():
    with pytest.raises(
        ValueError,
        match="API response must contain a 'data' field.",
    ):
        ingest_jobs.extract_job_records({})


@pytest.mark.parametrize(
    "data_value",
    [
        None,
        {},
        "not a list",
    ],
)
def test_extract_job_records_rejects_non_list_data(data_value):
    with pytest.raises(
        ValueError,
        match="API response 'data' field must be a list",
    ):
        ingest_jobs.extract_job_records({"data": data_value})


# ---
# Job validation and preparation tests
# ---
def test_prepare_job_trims_required_fields_and_preserves_raw_payload(
    valid_job,
):
    job = valid_job.copy()
    job["slug"] = "   data-engineer-123    "
    job["company_name"] = "  Example Company  "
    job["title"] = "  Data Engineer  "

    prepared_job = ingest_jobs.prepare_job(job)

    # Mapped database fields should use normalized required values
    assert prepared_job["source"] == "arbeitnow"
    assert prepared_job["source_job_id"] == "data-engineer-123"
    assert prepared_job["company_name"] == "Example Company"
    assert prepared_job["title"] == "Data Engineer"

    # The raw layer keeps the exact original API values before trimming
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


def test_prepare_job_stores_missing_optional_fields_as_none():
    job = {
        "slug": "backend-developer-123",
        "company_name": "Example Company",
        "title": "Backend Developer",
    }

    prepared_job = ingest_jobs.prepare_job(job)

    assert prepared_job["description"] is None
    assert prepared_job["location"] is None
    assert prepared_job["remote"] is None
    assert prepared_job["job_url"] is None
    assert prepared_job["posted_at_raw"] is None
    assert prepared_job["tags_raw"] is None
    assert prepared_job["job_types_raw"] is None


def test_prepare_job_preserves_empty_json_lists():
    job = {
        "slug": "software-engineer-123",
        "company_name": "Example Company",
        "title": "Software Engineer",
        "tags": [],
        "job_types": [],
    }

    prepared_job = ingest_jobs.prepare_job(job)

    assert prepared_job["tags_raw"] == "[]"
    assert prepared_job["job_types_raw"] == "[]"


# ---
# Insert and batch outcome tests
# ---
def test_insert_job_returns_true_when_record_is_inserted(valid_job):
    cur = MagicMock()
    cur.fetchone.return_value = (42,)

    prepared_job = ingest_jobs.prepare_job(valid_job)
    inserted = ingest_jobs.insert_job(cur, prepared_job)

    assert inserted is True
    assert cur.execute.call_count == 1

    # The SQL must return an ID so inserts and conflicts can be distinguished.
    sql = cur.execute.call_args.args[0]
    assert "ON CONFLICT (source_job_id) DO NOTHING" in sql
    assert "RETURNING id" in sql


def test_insert_job_returns_false_when_duplicate_is_skipped(valid_job):
    cur = MagicMock()
    cur.fetchone.return_value = None

    prepared_job = ingest_jobs.prepare_job(valid_job)
    inserted = ingest_jobs.insert_job(cur, prepared_job)

    assert inserted is False
    assert cur.execute.call_count == 1


def test_process_jobs_counts_inserted_duplicate_and_invalid_records(
    valid_job,
):
    inserted_job = valid_job.copy()

    invalid_job = valid_job.copy()
    invalid_job["slug"] = "   "

    duplicate_job = valid_job.copy()
    duplicate_job["slug"] = "existing-job-456"

    cur = MagicMock()

    # The first valid insert returns an ID; the second valid insert is a conflict.
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

    # Only the two valid records should execute SQL.
    assert cur.execute.call_count == 2


# ---
# Transaction and resource cleanup tests
# ---
def test_save_jobs_returns_counts_and_exits_transaction(valid_job):
    """Return batch counts and exit the transaction normally."""

    conn = MagicMock()
    cur = MagicMock()

    conn.__enter__.return_value = conn
    conn.cursor.return_value = cur
    cur.__enter__.return_value = cur
    cur.fetchone.return_value = (1,)

    with patch.object(
        ingest_jobs,
        "get_db_connection",
        return_value=conn,
    ):
        counts = ingest_jobs.save_jobs([valid_job])

    assert counts == {
        "fetched": 1,
        "inserted": 1,
        "duplicates_skipped": 0,
        "invalid_skipped": 0,
    }

    cur.__exit__.assert_called_once_with(None, None, None)
    conn.__exit__.assert_called_once_with(None, None, None)


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

    cur.__exit__.assert_called_once()
    conn.__exit__.assert_called_once()
    assert conn.__exit__.call_args == cur.__exit__.call_args
    assert conn.__exit__.call_args.args[0] is RuntimeError


# ---
# Main workflow and logging tests
# ---
def test_main_logs_success_summary(caplog):
    counts = {
        "fetched": 4,
        "inserted": 2,
        "duplicates_skipped": 1,
        "invalid_skipped": 1,
    }

    with (
        patch.object(
            ingest_jobs,
            "get_jobs",
            return_value={"data": []},
        ),
        patch.object(
            ingest_jobs,
            "save_jobs",
            return_value=counts,
        ) as save_jobs_mock,
        caplog.at_level(
            logging.INFO,
            logger=ingest_jobs.logger.name,
        ),
    ):
        result = ingest_jobs.main()

    assert result == counts
    save_jobs_mock.assert_called_once_with([])

    assert (
        "Ingestion complete: fetched=4 inserted=2 "
        "duplicates_skipped=1 invalid_skipped=1" in caplog.messages
    )


def test_main_logs_and_reraises_unexpected_failure(caplog):
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
