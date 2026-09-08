import logging
from unittest.mock import MagicMock, patch

import pytest

from pipeline import skill_extractor


@pytest.mark.parametrize(
    "text, expected",
    [
        (None, []),
        ("", []),
        ("   ", []),
        (123, []),
        ("JavaScript development and digital marketing.", []),
        ("Python developers use Python.", ["Python"]),
        (
            "Build PYTHON pipelines with sql and PostgreSQL",
            ["Python", "SQL", "PostgreSQL"],
        ),
    ],
)
def test_extract_skills_handles_edge_cases(text, expected):

    assert skill_extractor.extract_skills_from_text(text) == expected


def test_insert_skill_raises_when_existing_skill_cannot_be_found():

    cur = MagicMock()

    # INSERT or the fallback SELECT should not return a row
    cur.fetchone.side_effect = [
        None,
        None,
    ]

    with pytest.raises(
        RuntimeError,
        match="Could not retrieve skill ID for Python",
    ):
        skill_extractor.insert_skill(cur, "Python")


def test_save_skill_mappings_passes_failure_to_transaction_and_reraises():

    conn = MagicMock()
    cur = MagicMock()

    conn.__enter__.return_value = conn
    conn.cursor.return_value = cur
    cur.__enter__.return_value = cur

    with (
        patch.object(
            skill_extractor,
            "get_db_connection",
            return_value=conn,
        ),
        patch.object(
            skill_extractor,
            "process_cleaned_jobs",
            side_effect=RuntimeError("skill processing failed"),
        ),
        pytest.raises(
            RuntimeError,
            match="skill processing failed",
        ),
    ):
        skill_extractor.save_skill_mappings()

    cur.__exit__.assert_called_once()
    conn.__exit__.assert_called_once()

    assert conn.__exit__.call_args == cur.__exit__.call_args
    assert conn.__exit__.call_args.args[0] is RuntimeError


def test_main_logs_and_reraises_unexpected_failure(caplog):

    with (
        patch.object(
            skill_extractor,
            "save_skill_mappings",
            side_effect=RuntimeError("database unavailable"),
        ),
        caplog.at_level(
            logging.ERROR,
            logger=skill_extractor.logger.name,
        ),
        pytest.raises(
            RuntimeError,
            match="database unavailable",
        ),
    ):
        skill_extractor.main()

    assert "Skill extraction failed." in caplog.messages
