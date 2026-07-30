"""Transform raw job records into normalized rows in jobs_cleaned."""

import logging

from app.database import get_db_connection

logger = logging.getLogger(__name__)

# Accept realistic source publication times from 2000 through 2099.
MIN_VALID_EPOCH = 946_684_800
MAX_VALID_EPOCH = 4_102_444_799


def process_raw_jobs(cur) -> dict[str, int]:
    """Transform valid raw jobs and return data-quality outcome counts."""

    # Count all raw job records in this transformation run
    cur.execute("SELECT COUNT(*) FROM raw_jobs;")
    fetched = cur.fetchone()[0]

    # Count raw records that cannot be transformed because of one or more missing fields
    cur.execute("""
        SELECT COUNT(*)
        FROM raw_jobs
        WHERE
            -- Required fields must contain nonblank values.
            source IS NULL
            OR BTRIM(source) = ''
            OR source_job_id IS NULL
            OR BTRIM(source_job_id) = ''
            OR company_name IS NULL
            OR BTRIM(company_name) = ''
            OR title IS NULL
            OR BTRIM(title) = '';
        """)
    invalid_skipped = cur.fetchone()[0]

    # Count job records whose timestamp cannot be safely converted
    cur.execute(
        """
        SELECT COUNT(*)
        FROM raw_jobs
        WHERE
            source IS NOT NULL
            AND BTRIM(source) <> ''
            AND source_job_id IS NOT NULL
            AND BTRIM(source_job_id) <> ''
            AND company_name IS NOT NULL
            AND BTRIM(company_name) <> ''
            AND title IS NOT NULL
            AND BTRIM(title) <> ''
            AND posted_at_raw IS NOT NULL
            AND BTRIM(posted_at_raw) <> ''
            AND CASE
                WHEN BTRIM(posted_at_raw) ~ '^[0-9]+$'
                THEN NOT (
                    BTRIM(posted_at_raw)::NUMERIC
                    BETWEEN %s AND %s
                )
                ELSE TRUE
            END;
        """,
        (
            MIN_VALID_EPOCH,
            MAX_VALID_EPOCH,
        ),
    )
    invalid_timestamps = cur.fetchone()[0]

    # Normalize and insert valid raw records while skipping existing source IDs
    cur.execute(
        """
        INSERT INTO jobs_cleaned (
            raw_job_id,
            source,
            source_job_id,
            company_name,
            title,
            description,
            location,
            remote,
            job_url,
            posted_at
        )
        SELECT
            id,
            BTRIM(source),
            BTRIM(source_job_id),
            BTRIM(company_name),
            BTRIM(title),
            NULLIF(BTRIM(description), ''),
            NULLIF(BTRIM(location), ''),
            remote,
            NULLIF(BTRIM(job_url), ''),
            CASE
                WHEN BTRIM(posted_at_raw) ~ '^[0-9]+$'
                THEN CASE
                    WHEN BTRIM(posted_at_raw)::NUMERIC
                        BETWEEN %s AND %s
                    THEN
                        to_timestamp(
                            BTRIM(posted_at_raw)::DOUBLE PRECISION
                        ) AT TIME ZONE 'UTC'
                    ELSE NULL
                END
                ELSE NULL
            END
        FROM raw_jobs
        WHERE
            source IS NOT NULL
            AND BTRIM(source) <> ''
            AND source_job_id IS NOT NULL
            AND BTRIM(source_job_id) <> ''
            AND company_name IS NOT NULL
            AND BTRIM(company_name) <> ''
            AND title IS NOT NULL
            AND BTRIM(title) <> ''
        ON CONFLICT (source_job_id) DO NOTHING
        RETURNING id;
        """,
        (
            MIN_VALID_EPOCH,
            MAX_VALID_EPOCH,
        ),
    )

    inserted = len(cur.fetchall())
    duplicates_skipped = fetched - invalid_skipped - inserted

    return {
        "fetched": fetched,
        "inserted": inserted,
        "duplicates_skipped": duplicates_skipped,
        "invalid_skipped": invalid_skipped,
        "invalid_timestamps": invalid_timestamps,
    }


def transform_jobs() -> dict[str, int]:
    """Transform raw jobs in one transaction and return outcome counts."""

    conn = get_db_connection()
    cur = None

    try:
        cur = conn.cursor()
        counts = process_raw_jobs(cur)
        conn.commit()

        return counts

    except Exception:
        # Roll back the complete transformation after an unexpected database error
        conn.rollback()
        raise

    finally:
        if cur is not None:
            cur.close()

        conn.close()


def main() -> dict[str, int]:
    """Run transformation process and log the final outcome counts."""

    try:
        counts = transform_jobs()

    except Exception:
        logger.exception("Job transformation failed.")
        raise

    logger.info(
        "Transformation complete: fetched=%d inserted=%d "
        "duplicates_skipped=%d invalid_skipped=%d invalid_timestamps=%d",
        counts["fetched"],
        counts["inserted"],
        counts["duplicates_skipped"],
        counts["invalid_skipped"],
        counts["invalid_timestamps"],
    )

    return counts


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )

    main()
    