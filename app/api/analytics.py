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
    """Execute a read-only query, map psycopg failures to HTTP 503, and close created resources."""

    try:
        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute(query)

            return cur.fetchall()

    except psycopg.Error as ex:

        logger.exception("Analytics database query failed.")

        raise HTTPException(
            status_code=503, detail="Analytics data is temporarily unavailable"
        ) from ex


@router.get("/top-skills", response_model=list[SkillCount])
def get_top_skills():
    """Return the ten extracted skills mapped to the most cleaned jobs."""

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

    return [

        {"skill_name": row[0], "job_count": row[1]}
        for row in rows
    ]


@router.get("/top-titles", response_model=list[TitleCount])
def get_top_titles():
    """Return the ten most frequent exact title values in cleaned jobs."""

    rows = _fetch_all("""
        SELECT
            title,
            COUNT(*) AS job_count
        FROM jobs_cleaned
        GROUP BY title
        ORDER BY job_count DESC, title ASC
        LIMIT 10;
        """)

    return [
        {"title": row[0], "job_count": row[1]}
        for row in rows
    ]


@router.get("/remote-status", response_model=list[RemoteFlagCount])
def get_remote_status():
    """Return job counts grouped by the source-provided remote flag."""

    rows = _fetch_all("""
        SELECT
            remote,
            COUNT(*) AS job_count
        FROM jobs_cleaned
        GROUP BY remote
        ORDER BY remote DESC;
        """)

    return [
        {"remote": row[0], "job_count": row[1]}
        for row in rows
    ]
