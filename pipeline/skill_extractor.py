"""Extract skills from cleaned job text and store job-skill mappings."""

import logging
import re
from typing import Any

from app.database import get_db_connection

logger = logging.getLogger(__name__)

# A Fixed skill list
SKILLS = [
    "Python",
    "SQL",
    "Java",
    "AWS",
    "Azure",
    "GCP",
    "Spark",
    "Airflow",
    "Docker",
    "PostgreSQL",
    "FastAPI",
    "Git",
]


def extract_skills_from_text(text: Any) -> list[str]:
    """Return known skills found as complete terms in the supplied text."""

    if not isinstance(text, str) or not text.strip():
        return []

    matched_skills = []

    for skill in SKILLS:
        pattern = rf"\b{re.escape(skill)}\b"

        if re.search(pattern, text, re.IGNORECASE):
            matched_skills.append(skill)

    return matched_skills


def insert_skill(cur, skill_name: str) -> tuple[int, bool]:
    """Return the skill ID and whether a new skill row was inserted."""

    cur.execute(
        """
        INSERT INTO skills_extracted (skill_name)
        VALUES (%s)
        ON CONFLICT (skill_name) DO NOTHING
        RETURNING id;
        """,
        (skill_name,),
    )

    inserted_row = cur.fetchone()

    if inserted_row is not None:
        return inserted_row[0], True

    cur.execute(
        """
        SELECT id
        FROM skills_extracted
        WHERE skill_name = %s;
        """,
        (skill_name,),
    )

    existing_row = cur.fetchone()

    if existing_row is None:
        raise RuntimeError(f"Could not retrieve skill ID for {skill_name}")

    return existing_row[0], False


def insert_job_skill_map(cur, job_id: int, skill_id: int) -> bool:
    """Insert a job-skill mapping and return whether a new row  was created."""

    cur.execute(
        """
        INSERT INTO job_skill_map (job_id, skill_id)
        VALUES (%s, %s)
        ON CONFLICT (job_id, skill_id) DO NOTHING
        RETURNING job_id;
        """,
        (
            job_id,
            skill_id,
        ),
    )

    return cur.fetchone() is not None


def process_cleaned_jobs(cur) -> dict[str, int]:
    """Extract and store skills for all cleaned jobs."""

    # Load the text needed for skill matching
    cur.execute("""
        SELECT
            id,
            title,
            description
        FROM jobs_cleaned;
        """)

    jobs = cur.fetchall()

    counts = {
        "jobs_processed": len(jobs),
        "jobs_with_matches": 0,
        "skills_inserted": 0,
        "mappings_inserted": 0,
        "mappings_skipped": 0,
    }

    for job_id, title, description in jobs:
        full_text = f"{title} {description or ''}"
        matched_skills = extract_skills_from_text(full_text)

        if matched_skills:
            counts["jobs_with_matches"] += 1

        for skill in matched_skills:
            skill_id, skill_inserted = insert_skill(cur, skill)

            if skill_inserted:
                counts["skills_inserted"] += 1

            if insert_job_skill_map(cur, job_id, skill_id):
                counts["mappings_inserted"] += 1
            else:
                counts["mappings_skipped"] += 1

    return counts


def save_skill_mappings() -> dict[str, int]:
    """Process cleaned jobs in one transaction and return outcome counts."""

    conn = get_db_connection()
    cur = None

    try:
        cur = conn.cursor()
        counts = process_cleaned_jobs(cur)
        conn.commit()

        return counts

    except Exception:
        # Roll back all pending skill and mapping inserts after a failure
        conn.rollback()
        raise

    finally:
        if cur is not None:
            cur.close()

        conn.close()


def main() -> dict[str, int]:
    """Run skill extraction process and log the final outcome counts."""

    try:
        counts = save_skill_mappings()

    except Exception:
        logger.exception("Skill extraction failed.")
        raise

    logger.info(
        "Skill extraction complete: jobs_processed=%d jobs_with_matches=%d "
        "skills_inserted=%d mappings_inserted=%d mappings_skipped=%d",
        counts["jobs_processed"],
        counts["jobs_with_matches"],
        counts["skills_inserted"],
        counts["mappings_inserted"],
        counts["mappings_skipped"],
    )

    return counts


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )

    main()
