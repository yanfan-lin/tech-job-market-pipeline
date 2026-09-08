"""Test required environment settings and PostgreSQL connection creation."""

from unittest.mock import patch

import pytest

from app import database
from app.config import get_required_env


@pytest.mark.parametrize(
    "invalid_value",
    [
        None,
        "",
        " \t ",
    ],
)
def test_get_required_env_rejects_missing_or_blank_value(monkeypatch, invalid_value):

    if invalid_value is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", invalid_value)

    with pytest.raises(
        RuntimeError,
        match="Required environment variable DATABASE_URL is missing or blank",
    ):
        get_required_env("DATABASE_URL")


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
