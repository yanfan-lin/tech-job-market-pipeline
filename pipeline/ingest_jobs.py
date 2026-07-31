"""Fetch Arbeitnow job records and load accepted records into raw_jobs."""

import json
import logging
from typing import Any

import requests

from app.config import settings
from app.database import get_db_connection

logger = logging.getLogger(__name__)

# Reject records without a nonblank slug, company name, or title;
# slug becomes the unique source_job_id.
REQUIRED_FIELDS = ("slug", "company_name", "title")


def get_jobs() -> Any:
    """Fetch and decode one response from the configured job-source URL."""

    response = requests.get(settings.JOB_SOURCE_URL)

    response.raise_for_status()

    data = response.json()

    return data


def extract_job_records(raw_data: Any) -> list[Any]:
    """Validate the top-level API response and return its data list."""

    if not isinstance(raw_data, dict):
        raise ValueError("API response must be a JSON object.")

    if "data" not in raw_data:
        raise ValueError("API response must contain a 'data' field.")

    jobs = raw_data["data"]

    if not isinstance(jobs, list):
        raise ValueError("API response 'data' field must be a list.")

    return jobs


def serialize_optional_json(value: Any) -> str | None:
    """Serialize JSON data while preserving missing values as SQL NULL."""

    if value is None:
        return None

    return json.dumps(value)


def prepare_job(job: Any) -> dict[str, Any] | None:
    """Validate required fields and prepare mapped values while preserving the original record in raw_payload."""

    if not isinstance(job, dict):
        return None

    for field in REQUIRED_FIELDS:
        value = job.get(field)

        if not isinstance(value, str) or not value.strip():
            return None

    return {
        "source": "arbeitnow",
        "source_job_id": job["slug"].strip(),
        "company_name": job["company_name"].strip(),
        "title": job["title"].strip(),
        "description": job.get("description"),
        "location": job.get("location"),
        "remote": job.get("remote"),
        "job_url": job.get("url"),
        "posted_at_raw": job.get("created_at"),
        "tags_raw": serialize_optional_json(job.get("tags")),
        "job_types_raw": serialize_optional_json(job.get("job_types")),
        "raw_payload": json.dumps(job),
    }


def insert_job(cur, prepared_job: dict[str, Any]) -> bool:
    """Insert one prepared job and return whether a new row was created."""

    cur.execute(
        """
        INSERT INTO raw_jobs (
            source,
            source_job_id,
            company_name,
            title,
            description,
            location,
            remote,
            job_url,
            posted_at_raw,
            tags_raw,
            job_types_raw,
            raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_job_id) DO NOTHING
        RETURNING id;
        """,
        (
            prepared_job["source"],
            prepared_job["source_job_id"],
            prepared_job["company_name"],
            prepared_job["title"],
            prepared_job["description"],
            prepared_job["location"],
            prepared_job["remote"],
            prepared_job["job_url"],
            prepared_job["posted_at_raw"],
            prepared_job["tags_raw"],
            prepared_job["job_types_raw"],
            prepared_job["raw_payload"],
        ),
    )

    # RETURNING produces a row only when PostgreSQL inserts the record
    return cur.fetchone() is not None


def process_jobs(cur, jobs: list[Any]) -> dict[str, int]:
    """Validate source jobs, insert accepted records, and count outcomes."""

    counts = {
        "fetched": len(jobs),
        "inserted": 0,
        "duplicates_skipped": 0,
        "invalid_skipped": 0,
    }

    for job in jobs:
        prepared_job = prepare_job(job)

        if prepared_job is None:
            counts["invalid_skipped"] += 1
            continue

        if insert_job(cur, prepared_job):
            counts["inserted"] += 1
        else:
            counts["duplicates_skipped"] += 1

    return counts


def save_jobs(jobs: list[Any]) -> dict[str, int]:
    """Save valid jobs in one transaction and return the outcome counts."""

    conn = get_db_connection()
    cur = None

    try:
        cur = conn.cursor()
        counts = process_jobs(cur, jobs)
        conn.commit()

        return counts

    except Exception:
        # Roll back all pending inserts if batch processing or database work fails.
        conn.rollback()

        raise

    finally:
        if cur is not None:
            cur.close()

        conn.close()


def main() -> dict[str, int]:
    """Run ingestion and return the final outcome counts."""

    try:
        raw_data = get_jobs()
        jobs = extract_job_records(raw_data)
        counts = save_jobs(jobs)

    except Exception:
        logger.exception("Job ingestion failed.")
        raise

    logger.info(
        "Ingestion complete: fetched=%d inserted=%d "
        "duplicates_skipped=%d invalid_skipped=%d",
        counts["fetched"],
        counts["inserted"],
        counts["duplicates_skipped"],
        counts["invalid_skipped"],
    )

    return counts


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )

    main()
