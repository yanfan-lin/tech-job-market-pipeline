from pipeline import skill_extractor


def insert_cleaned_job(cur, source_job_id, title, description):
    """Insert a raw job and its corresponding cleaned record."""

    cur.execute(
        """
        INSERT INTO raw_jobs (
            source, source_job_id, company_name, title, description, raw_payload
        )
        VALUES ('arbeitnow', %s, 'Example Company', %s, %s, '{}'::jsonb)
        RETURNING id;
        """,
        (source_job_id, title, description),
    )

    raw_job_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO jobs_cleaned (
            raw_job_id, source, source_job_id, company_name, title, description
        )
        VALUES (%s, 'arbeitnow', %s, 'Example Company', %s, %s);
        """,
        (raw_job_id, source_job_id, title, description),
    )


def test_process_cleaned_jobs_avoids_false_matches_and_duplicates(db_cursor):

    insert_cleaned_job(
        db_cursor,
        "postgres-python-job",
        "Python Engineer",
        "Build SQL pipelines with Docker.",
    )

    # JavaScript and digital must not create Java or Git matches
    insert_cleaned_job(
        db_cursor,
        "postgres-marketing-job",
        "JavaScript Developer",
        "Create digital marketing tools.",
    )

    first_counts = skill_extractor.process_cleaned_jobs(db_cursor)
    assert first_counts == {
        "jobs_processed": 2,
        "jobs_with_matches": 1,
        "skills_inserted": 3,
        "mappings_inserted": 3,
        "mappings_skipped": 0,
    }

    db_cursor.execute("SELECT COUNT(*) FROM job_skill_map;")
    assert db_cursor.fetchone()[0] == 3

    # Rerunning must reuse the existing skills and mappings.
    second_counts = skill_extractor.process_cleaned_jobs(db_cursor)
    assert second_counts == {
        "jobs_processed": 2,
        "jobs_with_matches": 1,
        "skills_inserted": 0,
        "mappings_inserted": 0,
        "mappings_skipped": 3,
    }
    db_cursor.execute("SELECT skill_name FROM skills_extracted ORDER BY skill_name;")

    skill_names = [row[0] for row in db_cursor.fetchall()]
    assert skill_names == ["Docker", "Python", "SQL"]

    db_cursor.execute("SELECT COUNT(*) FROM job_skill_map;")
    assert db_cursor.fetchone()[0] == 3
