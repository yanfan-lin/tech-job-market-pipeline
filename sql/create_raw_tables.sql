-- Raw jobs table to store original job records from the source API
CREATE TABLE IF NOT EXISTS raw_jobs (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_job_id TEXT NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    location TEXT,
    remote BOOLEAN,
    job_url TEXT,
    posted_at_raw TEXT,
    tags_raw JSONB,
    job_types_raw JSONB,
    raw_payload JSONB NOT NULL,
    ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);