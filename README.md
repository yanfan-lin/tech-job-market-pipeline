# Tech Job Market Data Pipeline

[![My Skills](https://skillicons.dev/icons?i=py,postgres,fastapi,docker,regex,git,github)](https://skillicons.dev)

An end-to-end data pipeline that ingests job listings from the [Arbeitnow API](https://www.arbeitnow.com/api/job-board-api), stores raw and cleaned records in PostgreSQL, extracts known skills, and exposes aggregate results through FastAPI.

The project demonstrates data validation, relational modelling, idempotent writes, transaction handling, rule-based enrichment, and automated testing.

## Features

- Ingests job listings from the Arbeitnow API into PostgreSQL
- Validates required fields and preserves the original source payload
- Prevents duplicate jobs, skills, and job-skill mappings
- Cleans raw records and handles invalid optional timestamps safely
- Extracts skills using case-insensitive whole-term matching
- Exposes job-market aggregates through FastAPI
- Uses transactions, rollback handling, and outcome logging
- Includes mocked tests and real PostgreSQL integration tests

## Architecture and data flow

```text
Arbeitnow API
      ↓
   raw_jobs
      ↓
 jobs_cleaned
      ↓
skills_extracted + job_skill_map
      ↓
FastAPI analytics
```

1. **Ingest:** Validate API records and preserve the source payload in `raw_jobs`.
2. **Transform:** Clean valid records and load them into `jobs_cleaned`.
3. **Enrich:** Extract known skills and create job-to-skill mappings.
4. **Serve:** Query the processed tables through read-only FastAPI endpoints.

## Tech stack

- **Language:** Python
- **API:** FastAPI, Pydantic, Uvicorn
- **Database:** PostgreSQL, Psycopg, SQL
- **Data ingestion:** Requests, JSON, regular expressions
- **Testing:** pytest, unittest.mock, FastAPI TestClient, HTTPX
- **Development:** Docker Compose, Git, GitHub

## Project structure

```text
.
|-- app/
|   |-- api/
|   |   `-- analytics.py
|   |-- config.py
|   |-- database.py
|   `-- main.py
|-- pipeline/
|   |-- ingest_jobs.py
|   |-- transform_jobs.py
|   `-- skill_extractor.py
|-- sql/
|   |-- create_raw_tables.sql
|   `-- create_processed_tables.sql
|-- tests/
|   |-- test_analytics.py
|   |-- test_analytics_postgres.py
|   |-- test_config_database.py
|   |-- test_ingest_jobs.py
|   |-- test_skill_extractor.py
|   |-- test_skill_extractor_postgres.py
|   |-- test_transform_jobs.py
|   `-- test_transform_jobs_postgres.py
|-- .env.example
|-- docker-compose.yml
|-- requirements.txt
`-- README.md
```

## Database tables

### `raw_jobs`

Landing table for source API records.

- Stores the Arbeitnow slug as unique `source_job_id`.
- Keeps mapped scalar fields, JSONB tags and job types, and the original record in `raw_payload`.
- Retains the source timestamp as `posted_at_raw` text for later validation.
- Uses PostgreSQL `CURRENT_TIMESTAMP` in the timezone-naive `ingested_at` column when the raw row is inserted.

### `jobs_cleaned`

Normalized table used by transformation and analytics.

- References the originating `raw_jobs` row through `raw_job_id`.
- Enforces a unique `source_job_id`.
- Stores cleaned required and optional fields.
- Stores valid source timestamps as UTC-normalized, timezone-naive values in `posted_at`; unavailable or invalid values are `NULL`.
- Uses PostgreSQL `CURRENT_TIMESTAMP` in the timezone-naive `ingested_at` column when the cleaned row is inserted.

### `skills_extracted`

One row per unique skill name recognized by the rule-based extractor.

### `job_skill_map`

Many-to-many bridge between cleaned jobs and extracted skills. A unique `(job_id, skill_id)` constraint prevents duplicate relationships.

## Local setup on Windows PowerShell

### Prerequisites

- Python 3.10 or newer with `venv` support
- Docker Desktop with Docker Compose
- Git, if cloning the repository

Run all commands from the repository root.

### 1. Clone the repository

```powershell
git clone https://github.com/yanfan-lin/tech-job-market-pipeline.git
Set-Location tech-job-market-pipeline
```

### 2. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks local activation scripts, use a PowerShell session with an execution policy appropriate for your development environment, then rerun the activation command.

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Create the local environment file

```powershell
Copy-Item .env.example .env
```

The supplied local defaults target PostgreSQL on host port `5433`. Update `.env` if your local credentials, port, database names, or API URL differ.

The repository ignores `.env`; keep real credentials there and keep `.env.example` limited to safe local examples.

| Variable | Used by | Local example | Purpose |
|---|---|---|---|
| `DATABASE_URL` | Pipeline and API | `postgresql://postgres:postgres@localhost:5433/tech_jobs_db` | Main PostgreSQL connection string |
| `JOB_SOURCE_URL` | Ingestion | `https://www.arbeitnow.com/api/job-board-api` | Arbeitnow API endpoint |
| `TEST_DATABASE_URL` | Integration tests | `postgresql://postgres:postgres@localhost:5433/tech_jobs_test` | Dedicated test-only PostgreSQL database |

`DATABASE_URL` and `JOB_SOURCE_URL` must be present and nonblank when accessed. Configuration validation fails early with a concise `RuntimeError` rather than silently using an invalid value. Integration fixtures empty the project tables in `tech_jobs_test`, so never point `TEST_DATABASE_URL` at a database containing data you need.

### 5. Start PostgreSQL

```powershell
docker compose up -d db
docker compose exec -T db pg_isready -U postgres -d tech_jobs_db
```

Docker Compose runs PostgreSQL 16 on container port `5432`, published as host port `5433`. Data persists in the named `postgres_data` volume.

### 6. Apply the application schemas

```powershell
Get-Content -Raw .\sql\create_raw_tables.sql | docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d tech_jobs_db
Get-Content -Raw .\sql\create_processed_tables.sql | docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d tech_jobs_db
```

Apply the raw schema first because the processed schema creates a foreign key to `raw_jobs`.

### 7. Run the pipeline

Run the stages in order:

```powershell
python -m pipeline.ingest_jobs
python -m pipeline.transform_jobs
python -m pipeline.skill_extractor
```

These stages are invoked manually. The repository does not include scheduled orchestration.

### 8. Start FastAPI

```powershell
python -m uvicorn app.main:app --reload
```

Useful local URLs:

- Analytics route prefix: `http://127.0.0.1:8000/analytics`
- Interactive Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI document: `http://127.0.0.1:8000/openapi.json`

## Analytics endpoints

The examples below illustrate response shapes; counts depend on the locally processed data. When no matching rows exist, each endpoint returns `200 OK` with an empty JSON list.

### `GET /analytics/top-skills`

Returns up to ten skills ordered by descending job count, then ascending skill name for deterministic ties.

```json
[
  {
    "skill_name": "Python",
    "job_count": 24
  },
  {
    "skill_name": "SQL",
    "job_count": 18
  }
]
```

### `GET /analytics/top-titles`

Returns up to ten exact cleaned titles ordered by descending count, then ascending title for deterministic ties.

```json
[
  {
    "title": "Data Engineer",
    "job_count": 12
  },
  {
    "title": "Backend Engineer",
    "job_count": 9
  }
]
```

### `GET /analytics/remote-status`

Groups cleaned jobs by the nullable `remote` value supplied by the source. `true` and `false` preserve the corresponding source values, while `null` represents missing source information. It is not a location-text classifier.

The SQL orders the nullable flag descending. With all three groups present, PostgreSQL returns `null` first, followed by `true` and `false`.

```json
[
  {
    "remote": null,
    "job_count": 2
  },
  {
    "remote": true,
    "job_count": 30
  },
  {
    "remote": false,
    "job_count": 17
  }
]
```

If an analytics database query fails, the client receives:

```json
{
  "detail": "Analytics data is temporarily unavailable"
}
```

with HTTP status `503`; database exception details are not included in the response.

## Tests

### Unit and API tests without PostgreSQL integration tests

The following focused command runs mocked configuration, database, pipeline, and analytics tests without requiring a live PostgreSQL test database:

```powershell
python -m pytest `
    tests/test_config_database.py `
    tests/test_ingest_jobs.py `
    tests/test_transform_jobs.py `
    tests/test_skill_extractor.py `
    tests/test_analytics.py `
    -q
```

### Full suite with PostgreSQL integration tests

Docker Compose creates `tech_jobs_db` automatically, but it does not create `tech_jobs_test`. Create the dedicated test database once:

```powershell
docker compose exec -T db createdb -U postgres tech_jobs_test
```

If PostgreSQL reports that the database already exists, do not recreate it. Apply both schemas to the test database:

```powershell
Get-Content -Raw .\sql\create_raw_tables.sql | docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d tech_jobs_test
Get-Content -Raw .\sql\create_processed_tables.sql | docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d tech_jobs_test
```

Set the test connection explicitly and run the complete suite:

```powershell
$env:TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5433/tech_jobs_test"
python -m pytest -q
```

The integration fixtures require the database name to be exactly `tech_jobs_test`. They empty the project tables in that dedicated database and use rollback or explicit cleanup after testing, which is why the test URL must never target development data. With PostgreSQL running, both schemas applied, and `TEST_DATABASE_URL` configured, the current verified full-suite result is **91 passing tests**.


## Project highlights

- Layered PostgreSQL model with traceability from preserved source data to cleaned and enriched records.
- Validation, conflict-safe inserts, and transaction rollback make pipeline reruns predictable.
- Typed FastAPI responses, deterministic analytics queries, and generic database-error responses.
- Mocked unit tests and PostgreSQL integration tests protected by a dedicated test-database guard.

## Current scope and limitations

- Ingestion processes one API response per run; pagination and scheduling are not implemented.
- Pipeline writes are insert-only and do not synchronize source updates or remove stale mappings.
- Skill extraction uses a fixed vocabulary without contextual or synonym matching.
- Results come from one general job board and are not representative of the complete technology job market.
