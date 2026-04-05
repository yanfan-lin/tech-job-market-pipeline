# Tech Job Market Data Pipeline

## Overview
A small end-to-end data pipeline project that collects public job data from the [Arbeitnow API](https://www.arbeitnow.com/api/job-board-api), stores raw job records, transforms them into structured tables, and exposes simple analytics through FastAPI.


## Tech Stack 
- Python
- PostgreSQL
- SQL
- FastAPI
- Docker Compose
- psycopg
- Git


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
Use the values in `.env.example` to create your own `.env` file.

### 5. Start PostgreSQL with Docker Compose
```bash
docker compose up -d
```

### 6. Create the database tables
```bash
Get-Content sql/create_raw_tables.sql | docker compose exec -T db psql -U postgres -d tech_jobs_db
```
```bash
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


## Project Workflow
1. Fetch raw job data from the [Arbeitnow API](https://www.arbeitnow.com/api/job-board-api)
2. Store raw job records in the `raw_jobs` table
3. Transform raw records into cleaned job data in the `jobs_cleaned` table
4. Extract skills from job titles and descriptions
5. Store extracted skills and job-skill relationships in relational tables
6. Expose analytics endpoints through FastAPI


## Database Tables

- `raw_jobs`  
  Stores original job records collected from the API.  
  Key columns: `source_job_id`, `company_name`, `title`, `description`, `location`, `remote`, `posted_at_raw`, `raw_payload`

- `jobs_cleaned`  
  Stores cleaned job records transformed from the raw layer.  
  Key columns: `raw_job_id`, `source_job_id`, `company_name`, `title`, `description`, `location`, `remote`, `posted_at`

- `skills_extracted`  
  Stores unique extracted skill names.  
  Key columns: `id`, `skill_name`

- `job_skill_map`  
  Stores relationships between cleaned jobs and extracted skills.  
  Key columns: `job_id`, `skill_id`


## API Endpoints

After starting the FastAPI app, visit:
```bash
http://127.0.0.1:8000/docs
```


Available analytics endpoints:
- `/analytics/top-skills`
  Returns the top 10 most common skills extracted from job titles and descriptions

- `/analytics/top-titles`
  Returns the top 10 most common job titles

- `/analytics/remote-vs-onsite`
  Returns counts of remote and non-remote jobs

