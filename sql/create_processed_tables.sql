-- Cleaned jobs table for processed job records
CREATE TABLE IF NOT EXISTS jobs_cleaned (
    id SERIAL PRIMARY KEY,
    raw_job_id INTEGER NOT NULL REFERENCES raw_jobs(id),
    source TEXT NOT NULL,
    source_job_id TEXT NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    location TEXT,
    remote BOOLEAN,
    job_url TEXT,
    posted_at TIMESTAMP,
    ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- Table to store extracted skills
CREATE TABLE IF NOT EXISTS skills_extracted (
    id SERIAL PRIMARY KEY,
    skill_name TEXT NOT NULL UNIQUE
);


-- Table mapping cleaned jobs to extracted skills
CREATE TABLE IF NOT EXISTS job_skill_map (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs_cleaned(id),
    skill_id INTEGER NOT NULL REFERENCES skills_extracted(id),
    UNIQUE (job_id, skill_id)
)