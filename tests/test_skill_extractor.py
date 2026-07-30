import logging
from unittest.mock import MagicMock, patch

import pytest

from pipeline import skill_extractor


def test_extract_skills_matches_complete_terms_case_insensitively():
    text = "Build PYTHON pipelines with sql and PostgreSQL"

    matched_skills = skill_extractor.extract_skills_from_text(text)

    assert matched_skills == [
        "Python",
        "SQL",
        "PostgreSQL",
    ]


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "   ",
        123,
    ],
)
def test_extract_skills_returns_empty_list_for_missing_or_invalid_text(text):
    assert skill_extractor.extract_skills_from_text(text) == []


def test_extract_skills_does_not_match_skill_inside_another_word():
    text = "JavaScript development and digital marketing experience."

    matched_skills = skill_extractor.extract_skills_from_text(text)

    assert "Java" not in matched_skills
    assert "Git" not in matched_skills


def test_extract_skills_returns_each_skill_only_once():
    text = "Python developers use Python for many Python applications."

    matched_skills = skill_extractor.extract_skills_from_text(text)

    assert matched_skills == ["Python"]


def test_insert_skill_returns_new_skill_id():
    cur = MagicMock()

    # PostgreSQL returns the ID created by INSERT ... RETURNING
    cur.fetchone.return_value = (12,)

    result = skill_extractor.insert_skill(cur, "Python")

    assert result == (12, True)
    assert cur.execute.call_count == 1


def test_insert_skill_returns_existing_skill_id_after_conflict():
    cur = MagicMock()

    # First fetch: INSERT returned nothing because the skill already exists.
    # Second fetch: SELECT returned the existing skill ID
    cur.fetchone.side_effect = [
        None,
        (12,),
    ]

    result = skill_extractor.insert_skill(cur, "Python")

    assert result == (12, False)
    assert cur.execute.call_count == 2


def test_insert_skill_raises_when_existing_skill_cannot_be_found():
    cur = MagicMock()

    # Neither INSERT nor the fallback SELECT returns a row
    cur.fetchone.side_effect = [
        None,
        None,
    ]

    with pytest.raises(
        RuntimeError,
        match="Could not retrieve skill ID for Python",
    ):
        skill_extractor.insert_skill(cur, "Python")


def test_insert_job_skill_map_returns_true_when_mapping_is_inserted():
    cur = MagicMock()
    cur.fetchone.return_value = (7,)

    inserted = skill_extractor.insert_job_skill_map(
        cur,
        job_id=7,
        skill_id=12,
    )

    assert inserted is True
    assert cur.execute.call_count == 1


def test_insert_job_skill_map_returns_false_when_mapping_already_exists():
    cur = MagicMock()
    cur.fetchone.return_value = None

    inserted = skill_extractor.insert_job_skill_map(
        cur,
        job_id=7,
        skill_id=12,
    )

    assert inserted is False
    assert cur.execute.call_count == 1


def test_process_cleaned_jobs_returns_outcome_counts():
    cur = MagicMock()

    cur.fetchall.return_value = [
        (
            1,
            "Python Engineer",
            "Build SQL pipelines.",
        ),
        (
            2,
            "Marketing Specialist",
            "Digital campaign experience.",
        ),
        (
            3,
            "Java Developer",
            None,
        ),
    ]

    with (
        patch.object(
            skill_extractor,
            "insert_skill",
            side_effect=[
                (10, True),
                (11, False),
                (12, True),
            ],
        ) as insert_skill_mock,
        patch.object(
            skill_extractor,
            "insert_job_skill_map",
            side_effect=[
                True,
                False,
                True,
            ],
        ) as insert_mapping_mock,
    ):
        counts = skill_extractor.process_cleaned_jobs(cur)

    assert counts == {
        "jobs_processed": 3,
        "jobs_with_matches": 2,
        "skills_inserted": 2,
        "mappings_inserted": 2,
        "mappings_skipped": 1,
    }

    assert cur.execute.call_count == 1
    assert insert_skill_mock.call_count == 3
    assert insert_mapping_mock.call_count == 3


def test_save_skill_mappings_commits_and_closes_resources():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur

    expected_counts = {
        "jobs_processed": 3,
        "jobs_with_matches": 2,
        "skills_inserted": 2,
        "mappings_inserted": 3,
        "mappings_skipped": 1,
    }

    with (
        patch.object(
            skill_extractor,
            "get_db_connection",
            return_value=conn,
        ),
        patch.object(
            skill_extractor,
            "process_cleaned_jobs",
            return_value=expected_counts,
        ) as process_mock,
    ):
        result = skill_extractor.save_skill_mappings()

    assert result == expected_counts
    process_mock.assert_called_once_with(cur)

    conn.commit.assert_called_once_with()
    conn.rollback.assert_not_called()
    cur.close.assert_called_once_with()
    conn.close.assert_called_once_with()


def test_save_skill_mappings_rolls_back_closes_resources_and_reraises():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur

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

    conn.commit.assert_not_called()
    conn.rollback.assert_called_once_with()
    cur.close.assert_called_once_with()
    conn.close.assert_called_once_with()


def test_main_logs_success_summary(caplog):
    counts = {
        "jobs_processed": 3,
        "jobs_with_matches": 2,
        "skills_inserted": 2,
        "mappings_inserted": 3,
        "mappings_skipped": 1,
    }

    with (
        patch.object(
            skill_extractor,
            "save_skill_mappings",
            return_value=counts,
        ),
        caplog.at_level(
            logging.INFO,
            logger=skill_extractor.logger.name,
        ),
    ):
        result = skill_extractor.main()

    assert result == counts
    assert (
        "Skill extraction complete: jobs_processed=3 jobs_with_matches=2 "
        "skills_inserted=2 mappings_inserted=3 mappings_skipped=1" in caplog.messages
    )


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
