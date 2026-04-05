# Load project settings from environment variables

import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

class Settings:
    # PostgreSQL connection URL
    DATABASE_URL = os.getenv("DATABASE_URL")

    # Job source API URL
    JOB_SOURCE_URL = os.getenv("JOB_SOURCE_URL")

# settings object to be used across the project
settings = Settings()

