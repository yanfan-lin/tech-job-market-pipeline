# Tech Job Market Data Pipeline

## Overview
A small ETL-style project that ingests public job listings, stores raw source data, cleans and normalizes job records, extracts skills from job text, and exposes simple analytics through a FastAPI app.

The pipeline uses [Arbeitnow API](https://www.arbeitnow.com/api/job-board-api) and PostgreSQL as the storage backend. It is intended to demonstrate a complete data flow from ingestion to analytics, without pretending to be a production-grade system.


## Tech Stack 
- Python
- FastAPI
- PostgreSQL
- Docker Compose
- SQL
- psycopg
- Git
- requests
- python-dotenv
- uvicorn


## Project Structure

- docker-compose.yml — starts local PostgreSQL
- requirements.txt — Python dependencies
- .env.example — example environment variables

app/
- `main.py` — FastAPI application entry point
- config.py — loads environment variables from .env
- database.py — PostgreSQL connection helper
- `api/analytics.py` — read-only analytics endpoints

pipeline/
- `ingest_jobs.py` — fetches job data from the Arbeitnow API into `raw_jobs`
- `transform_jobs.py` — transforms `raw_jobs` into `jobs_cleaned`
- `skill_extractor.py` — extracts skills and creates job-skill mappings

sql/
- `create_raw_tables.sql` — creates `raw_jobs`
- `create_processed_tables.sql` — creates cleaned and analytics-ready tables


## Setup Instructions

### 1. Clone the repository
```bash
git clone https://github.com/yanfan-lin/tech-job-market-pipeline.git
cd tech-job-market-pipeline
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Create a `.env` file
Copy `.env.example` to `.env` and keep the same variables:
- `DATABASE_URL`
- `JOB_SOURCE_URL`
  
Example values from `.env.example`:
```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/tech_jobs_db
JOB_SOURCE_URL=https://www.arbeitnow.com/api/job-board-api
```

### 5. Start PostgreSQL with Docker Compose
This project includes a `docker-compose.yml` that starts a PostgreSQL service:
- Service: `db`
- Image: `postgres:16`
- Host port: `5433`
- Container port: `5432`
- Database: `tech_jobs_db`
- User: `postgres`
- Password: `postgres`

Start the database:
```bash
docker compose up -d
```

### 6. Create the database tables

After PostgreSQL is running, create the raw and processed tables:

Run these commands in PowerShell on Windows:
```powershell
Get-Content sql/create_raw_tables.sql | docker compose exec -T db psql -U postgres -d tech_jobs_db
```

```powershell
Get-Content sql/create_processed_tables.sql | docker compose exec -T db psql -U postgres -d tech_jobs_db
```

### 7. Run the pipeline scripts
```bash
python -m pipeline.ingest_jobs
python -m pipeline.transform_jobs
python -m pipeline.skill_extractor
```

### 8. Start the FastAPI app
Start the local server with:
```bash
uvicorn app.main:app --reload
```

### 9. Open the API docs
Visit:
```
http://127.0.0.1:8000/docs
```


## Pipeline Data Workflow

Arbeitnow API

↓

raw_jobs

↓

jobs_cleaned

↓

skills_extracted + job_skill_map

↓

FastAPI analytics endpoints

1. Ingest raw job data from [Arbeitnow API](https://www.arbeitnow.com/api/job-board-api)
2. Store raw job records in `raw_jobs`
3. Transform raw records into cleaned rows in `jobs_cleaned`
4. Extract skills from job titles and descriptions
5. Store extracted skills in `skills_extracted`
6. Store job-to-skill links in `job_skill_map`
7. Expose analytics from the cleaned/processed tables via FastAPI


## Database Tables

- `raw_jobs`  
  Stores original job listings from the source API
  Includes parsed raw fields and the full raw JSON payload  
  Key columns: `source_job_id`, `company_name`, `title`, `description`, `location`, `remote`, `posted_at_raw`, `raw_payload`

- `jobs_cleaned`  
  Stores cleaned job records
  Derived from `raw_jobs`
  Key columns: `raw_job_id`, `source_job_id`, `company_name`, `title`, `description`, `location`, `remote`, `posted_at`

- `skills_extracted`  
  Stores unique extracted skill names 
  Key columns: `skill_name`

- `job_skill_map`  
  Maps cleaned jobs to extracted skills  
  Key columns: `job_id` - reference to `jobs_cleaned.id`, 
              `skill_id` - reference to `skills_extracted.id`


## FastAPI Analytics Endpoints

After starting the FastAPI app, visit:
```bash
http://127.0.0.1:8000/docs
```

The app exposes analytics under `/analytics`

- GET `/analytics/top-skills`
  Returns the top 10 extracted skills by job count

  Example curl:
  ```bash
  curl http://127.0.0.1:8000/analytics/top-skills
  ```

  Example response shape:
  ```json
  [
    {"skill_name": "Python", "job_count": 12},
    {"skill_name": "SQL", "job_count": 9}
  ]
  ```


- GET `/analytics/top-titles`
  Returns the top 10 most common job titles

  Example curl:
  ```bash
  curl http://127.0.0.1:8000/analytics/top-titles
  ```

  Example response shape:
  ```json
  [
    {"title": "Software Engineer", "job_count": 8},
    {"title": "Data Engineer", "job_count": 5}
  ]
  ```

- GET `/analytics/remote-vs-onsite`
  Returns counts of remote vs non-remote jobs

  Example curl:
  ```bash
  curl http://127.0.0.1:8000/analytics/remote-vs-onsite
  ```

  Example response shape:
  ```json
  [
    {"remote": true, "job_count": 20},
    {"remote": false, "job_count": 15}
  ]
  ```


## Project Limitations

- Skill extraction uses a fixed skill list and simple substring matching.
- It does not use advanced NLP, synonym matching, or entity extraction.
- The pipeline is designed for local development and analytics demos, not production deployment.
- Re-running the pipeline does not update existing cleaned rows; duplicates are skipped by source ID.
- The API is read-only and does not accept query parameters for analytics.


## What This Project Demonstrates
- A basic ETL pipeline from API ingestion to analytics reports
- Raw data capture and a cleaned/processed data layer
- Simple relational schema design in PostgreSQL
- Fixed-list skill extraction from job text
- A minimal FastAPI analytics service
- Using environment variables and Docker Compose for local setup