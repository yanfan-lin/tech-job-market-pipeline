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


def test_transform_jobs_commits_and_closes_resources():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur

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

    conn.commit.assert_called_once_with()
    conn.rollback.assert_not_called()
    cur.close.assert_called_once_with()
    conn.close.assert_called_once_with()


def test_transform_jobs_rolls_back_closes_resources_and_reraises():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur

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

    conn.commit.assert_not_called()
    conn.rollback.assert_called_once_with()
    cur.close.assert_called_once_with()
    conn.close.assert_called_once_with()


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
