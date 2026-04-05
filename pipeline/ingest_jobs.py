# Fetch raw job data from the job source API,
# and lo it into the raw_jobs table

import requests
import json

# Import project settings
from app.config import settings

# Database connection helper
from app.database import get_db_connection


def get_jobs():
    # Send a GET request to the job source API
    response = requests.get(settings.JOB_SOURCE_URL)

    # Raise error if request failed
    response.raise_for_status()

    # Convert JSON response into Python dictionary
    data = response.json()

    return data


def insert_job(cur, job):

    # Insert one raw job record into raw_jobs table
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
        ON CONFLICT (source_job_id) DO NOTHING;
        """,
        (
            "arbeitnow",
            job["slug"],
            job["company_name"],
            job["title"],
            job["description"],
            job["location"],
            job["remote"],
            job["url"],
            job["created_at"],
            json.dumps(job["tags"]),
            json.dumps(job["job_types"]),
            json.dumps(job),
        )
    )


def main():
    # Fetch raw data from API
    raw_data = get_jobs()

    # Get the list of job records from API response
    jobs = raw_data["data"]

    conn = get_db_connection()
    cur = conn.cursor()

    # Insert each job into the raw_jobs table
    for job in jobs:
        insert_job(cur, job)


    conn.commit()

    cur.close()
    conn.close()

    print(f"Inserted {len(jobs)} jobs into raw_jobs.")



if __name__ == "__main__":
    main()