# FastAPI router for analytics endpoints
from fastapi import APIRouter
from app.database import get_db_connection


router = APIRouter()

# Return TOP 10 most common skills extracted from job description
@router.get("/top-skills")
def get_top_skills():

    conn = get_db_connection()
    cur = conn.cursor()

    # Count how many jobs matched each skill
    cur.execute(
        """
        SELECT
            se.skill_name,
            COUNT(*) AS job_count
        FROM job_skill_map jsm
        JOIN skills_extracted se
            ON jsm.skill_id = se.id
        GROUP BY se.skill_name
        ORDER BY job_count DESC, se.skill_name ASC
        LIMIT 10;
        """
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for row in rows:
        result.append({
            "skill_name": row[0],
            "job_count": row[1]
        })

    return result


# Return Top 10 most common job titles
@router.get("/top-titles")
def get_top_titles():

    conn = get_db_connection()
    cur = conn.cursor()

    # Count the most common job titles
    cur.execute(
        """
        SELECT
            title,
            COUNT(*) AS job_count
        FROM jobs_cleaned
        GROUP BY title
        ORDER BY job_count DESC, title ASC
        LIMIT 10;
        """
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for row in rows:
        result.append({
            "title": row[0],
            "job_count": row[1]
        })
    
    return result


# Return counts of remote jobs vs on-site jobs
@router.get("/remote-vs-onsite")
def get_remote_vs_onsite():

    conn = get_db_connection()
    cur = conn.cursor()

    # Count remote jobs and on-site jobs
    cur.execute(
        """
        SELECT
            remote,
            COUNT(*) AS job_count
        FROM jobs_cleaned
        GROUP BY remote
        ORDER BY remote DESC;
        """
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for row in rows:
        result.append({
            "remote": row[0],
            "job_count": row[1]
        })

    return result



