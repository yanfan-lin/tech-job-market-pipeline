"""Expose read-only analytics endpoints for processed job market data."""

import logging

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter()


class SkillCount(BaseModel):
    """Represent the number of jobs associated with one extracted skill."""

    skill_name: str
    job_count: int


class TitleCount(BaseModel):
    """Represent the number of jobs associated with one job title."""

    title: str
    job_count: int


class RemoteFlagCount(BaseModel):
    """Represent the number of jobs for one source-provided remote flag."""

    remote: bool | None
    job_count: int


def _fetch_all(query: str):
    """Execute an analytics query and always close database resources."""

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query)

        return cur.fetchall()

    except psycopg.Error as exc:
        logger.exception("Analytics database query failed.")

        raise HTTPException(
            status_code=503,
            detail="Analytics data is temporarily unavailable",
        ) from exc

    finally:
        # Close resources that were successfully created
        if cur is not None:
            cur.close()

        if conn is not None:
            conn.close()


# Return the TOP 10 most common extracted skills
@router.get("/top-skills", response_model=list[SkillCount])
def get_top_skills():
    rows = _fetch_all("""
        SELECT
            se.skill_name,
            COUNT(*) AS job_count
        FROM job_skill_map jsm
        JOIN skills_extracted se
            ON jsm.skill_id = se.id
        GROUP BY se.skill_name
        ORDER BY job_count DESC, se.skill_name ASC
        LIMIT 10;
        """)

    result = []

    for row in rows:
        result.append(
            {
                "skill_name": row[0],
                "job_count": row[1],
            }
        )

    return result


# Return the Top 10 most common job titles
@router.get("/top-titles", response_model=list[TitleCount])
def get_top_titles():
    rows = _fetch_all("""
        SELECT
            title,
            COUNT(*) AS job_count
        FROM jobs_cleaned
        GROUP BY title
        ORDER BY job_count DESC, title ASC
        LIMIT 10;
        """)

    result = []

    for row in rows:
        result.append(
            {
                "title": row[0],
                "job_count": row[1],
            }
        )

    return result


# Return counts of remote jobs and non-remote jobs
@router.get("/remote-status", response_model=list[RemoteFlagCount])
def get_remote_status():
    rows = _fetch_all("""
        SELECT
            remote,
            COUNT(*) AS job_count
        FROM jobs_cleaned
        GROUP BY remote
        ORDER BY remote DESC;
        """)

    result = []

    for row in rows:
        result.append(
            {
                "remote": row[0],
                "job_count": row[1],
            }
        )

    return result
