import logging
from unittest.mock import MagicMock, patch

import pytest

from pipeline import transform_jobs


def test_process_raw_jobs_returns_outcome_counts():
    cur = MagicMock()

    # Results from the three SELECT COUNT(*) queries.
    cur.fetchone.side_effect = [
        (6,),  # Total raw records
        (1,),  # Invalid required-field records
        (2,),  # Invalid timestamps
    ]

    # IDs returned by the final INSERT statement.
    cur.fetchall.return_value = [
        (101,),
        (102,),
    ]

    counts = transform_jobs.process_raw_jobs(cur)

    assert counts == {
        "fetched": 6,
        "inserted": 2,
        "duplicates_skipped": 3,
        "invalid_skipped": 1,
        "invalid_timestamps": 2,
    }

    assert cur.execute.call_count == 4
    assert cur.fetchone.call_count == 3
    cur.fetchall.assert_called_once_with()


def test_transform_jobs_returns_counts_and_exits_transaction():

    conn = MagicMock()
    cur = MagicMock()

    conn.__enter__.return_value = conn

    conn.cursor.return_value = cur

    cur.__enter__.return_value = cur

    expected_counts = {
        "fetched": 6,
        "inserted": 2,
        "duplicates_skipped": 3,
        "invalid_skipped": 1,
        "invalid_timestamps": 2,
    }

    with (
        patch.object(
            transform_jobs,
            "get_db_connection",
            return_value=conn,
        ),
        patch.object(
            transform_jobs,
            "process_raw_jobs",
            return_value=expected_counts,
        ) as process_mock,
    ):
        result = transform_jobs.transform_jobs()

    assert result == expected_counts
    process_mock.assert_called_once_with(cur)

    cur.__exit__.assert_called_once_with(None, None, None)
    conn.__exit__.assert_called_once_with(None, None, None)


def test_transform_jobs_passes_failure_to_transaction_and_reraises():
    conn = MagicMock()
    cur = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value = cur
    cur.__enter__.return_value = cur

    with (
        patch.object(
            transform_jobs,
            "get_db_connection",
            return_value=conn,
        ),
        patch.object(
            transform_jobs,
            "process_raw_jobs",
            side_effect=RuntimeError("transformation failed"),
        ),
        pytest.raises(
            RuntimeError,
            match="transformation failed",
        ),
    ):
        transform_jobs.transform_jobs()

    cur.__exit__.assert_called_once()

    conn.__exit__.assert_called_once()

    assert conn.__exit__.call_args == cur.__exit__.call_args

    assert conn.__exit__.call_args.args[0] is RuntimeError


def test_main_logs_success_summary(caplog):
    counts = {
        "fetched": 6,
        "inserted": 2,
        "duplicates_skipped": 3,
        "invalid_skipped": 1,
        "invalid_timestamps": 2,
    }

    with (
        patch.object(
            transform_jobs,
            "transform_jobs",
            return_value=counts,
        ),
        caplog.at_level(
            logging.INFO,
            logger=transform_jobs.logger.name,
        ),
    ):
        result = transform_jobs.main()

    assert result == counts
    assert (
        "Transformation complete: fetched=6 inserted=2 "
        "duplicates_skipped=3 invalid_skipped=1 invalid_timestamps=2" in caplog.messages
    )


def test_main_logs_and_reraises_unexpected_failure(caplog):
    with (
        patch.object(
            transform_jobs,
            "transform_jobs",
            side_effect=RuntimeError("database unavailable"),
        ),
        caplog.at_level(
            logging.ERROR,
            logger=transform_jobs.logger.name,
        ),
        pytest.raises(
            RuntimeError,
            match="database unavailable",
        ),
    ):
        transform_jobs.main()

    assert "Job transformation failed." in caplog.messages
