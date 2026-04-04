import requests
import json

# Import project settings
from app.config import settings

# Database connection helper
from app.database import get_db_connection


def get_jobs():
    # Send request to the source API
    response = requests.get(settings.JOB_SOURCE_URL)

    # Raise error if failed
    response.raise_for_status()

    # Convert JSON response into Python dict
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
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

    # Open database connection
    conn = get_db_connection()

    # Create cursor
    cur = conn.cursor()

    # Insert one first job
    insert_job(cur, jobs[0])

    conn.commit()

    cur.close()
    conn.close()

    print("Inserted 1 job into raw_jobs ")



if __name__ == "__main__":
    main()