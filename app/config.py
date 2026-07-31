"""Load required project settings from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()


def _get_required_env(name: str) -> str:
    """Return a required variable or raise an error."""

    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(f"Required environment variable {name} is missing or blank")

    return value.strip()


class Settings:
    @property
    def DATABASE_URL(self) -> str:
        """Return the PostgreSQL connection URL."""

        return _get_required_env("DATABASE_URL")

    @property
    def JOB_SOURCE_URL(self) -> str:
        """Return the job-source API URL."""

        return _get_required_env("JOB_SOURCE_URL")


settings = Settings()
