import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

class Settings:
    # Database connection for PostgreSQL
    DATABASE_URL = os.getenv("DATABASE_URL")

    # API endpoint for job source
    JOB_SOURCE_URL = os.getenv("JOB_SOURCE_URL")

# settings object to be used across the project
settings = Settings()

