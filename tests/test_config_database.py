"""Test required environment settings and PostgreSQL connection creation."""

from unittest.mock import MagicMock, patch

import psycopg
import pytest

from app import database
from app.config import Settings


# Verify settings are read when accessed instead of being captured during import
def test_settings_returns_current_environment_values(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://test-user:test-password@localhost:5433/test-db",
    )
    monkeypatch.setenv(
        "JOB_SOURCE_URL",
        "https://example.com/jobs",
    )

    settings = Settings()

    assert (
        settings.DATABASE_URL
        == "postgresql://test-user:test-password@localhost:5433/test-db"
    )

    assert settings.JOB_SOURCE_URL == "https://example.com/jobs"


# Cover missing, empty, and whitespace-only configuration values
@pytest.mark.parametrize(
    "invalid_value",
    [
        None,
        "",
        " ",
        "\t",
    ],
)
def test_database_url_rejects_missing_or_blank_value(monkeypatch, invalid_value):
    if invalid_value is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", invalid_value)

    settings = Settings()

    with pytest.raises(
        RuntimeError,
        match="Required environment variable DATABASE_URL is missing or blank",
    ):
        _ = settings.DATABASE_URL


# Cover missing, empty, and whitespace-only configuration values
@pytest.mark.parametrize(
    "invalid_value",
    [
        None,
        "",
        " ",
        "\t",
    ],
)
def test_job_source_url_rejects_missing_or_blank_value(
    monkeypatch,
    invalid_value,
):
    if invalid_value is None:
        monkeypatch.delenv("JOB_SOURCE_URL", raising=False)
    else:
        monkeypatch.setenv("JOB_SOURCE_URL", invalid_value)

    settings = Settings()

    with pytest.raises(
        RuntimeError,
        match="Required environment variable JOB_SOURCE_URL is missing or blank",
    ):
        _ = settings.JOB_SOURCE_URL


def test_get_db_connection_uses_validated_database_url(monkeypatch):
    database_url = "postgresql://test-user:test-password@localhost:5433/test-db"
    monkeypatch.setenv("DATABASE_URL", database_url)

    # Mock psycopg so this test does not open a real database connection
    expected_connection = MagicMock()

    with patch.object(
        database.psycopg,
        "connect",
        return_value=expected_connection,
    ) as connect_mock:
        result = database.get_db_connection()

    assert result is expected_connection
    connect_mock.assert_called_once_with(database_url)


def test_get_db_connection_rejects_invalid_database_url_before_connecting(
    monkeypatch,
):
    monkeypatch.setenv("DATABASE_URL", "   ")

    # Validation must fail before psycopg attempts a connection
    with (
        patch.object(database.psycopg, "connect") as connect_mock,
        pytest.raises(
            RuntimeError,
            match="Required environment variable DATABASE_URL is missing or blank",
        ),
    ):
        database.get_db_connection()

    connect_mock.assert_not_called()


def test_get_db_connection_propagates_connection_errors(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://test-user:test-password@localhost:5433/test-db",
    )

    # Preserve the original psycopg error for higher-level pipeline handling
    with (
        patch.object(
            database.psycopg,
            "connect",
            side_effect=psycopg.OperationalError("database unavailable"),
        ),
        pytest.raises(
            psycopg.OperationalError,
            match="database unavailable",
        ),
    ):
        database.get_db_connection()
