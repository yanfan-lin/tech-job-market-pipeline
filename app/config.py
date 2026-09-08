"""Load required project settings from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()


def get_required_env(name: str) -> str:
    """Return a stripped environment value, reject missing or blank settings."""

    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(f"Required environment variable {name} is missing or blank")

    return value.strip()
