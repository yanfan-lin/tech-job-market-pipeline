# Transform raw job records into cleaned job data in the jobs_cleaned table

# Import database connection helper
from app.database import get_db_connection


def transform_jobs():
    # Open database connection
    conn = get_db_connection()

    # Create cursor to run SQL
    cur = conn.cursor()

    # Insert cleaned jobs from raw_jobs into jobs_cleaned
    cur.execute(
        """
        INSERT INTO jobs_cleaned(
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
            source,
            source_job_id,
            company_name,
            title,
            description,
            location,
            remote,
            job_url,
            to_timestamp(posted_at_raw::bigint)
        FROM raw_jobs
        ON CONFLICT (source_job_id) DO NOTHING;
        """
    )

    conn.commit()

    cur.close()
    conn.close()

    print("Transformed raw_jobs into jobs_cleaned.")



if __name__ == "__main__":
    transform_jobs()