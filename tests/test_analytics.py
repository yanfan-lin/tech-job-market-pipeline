"""Verify analytics failure responses and database context cleanup."""

from unittest.mock import MagicMock, patch

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.api import analytics
from app.main import app

# Keep server errors as responses so unexpected HTTP 500s fail the assertions
client = TestClient(app, raise_server_exceptions=False)


def create_mock_connection():
    """Return a mock connection and cursor configured for context managers."""

    conn = MagicMock()
    cur = MagicMock()

    conn.__enter__.return_value = conn
    conn.cursor.return_value = cur
    cur.__enter__.return_value = cur

    return conn, cur


@pytest.mark.parametrize(
    "path",
    [
        "/analytics/top-skills",
        "/analytics/top-titles",
        "/analytics/remote-status",
    ],
)
@pytest.mark.parametrize("operation", ["execute", "fetchall"])
def test_analytics_endpoints_handle_query_and_fetch_failures(path, operation):

    conn, cur = create_mock_connection()
    error = psycopg.DatabaseError("critical database failure")

    if operation == "execute":
        cur.execute.side_effect = error
    else:
        cur.fetchall.side_effect = error

    with patch.object(analytics, "get_db_connection", return_value=conn):
        response = client.get(path)

    assert response.status_code == 503
    assert response.json() == {"detail": "Analytics data is temporarily unavailable"}

    # Database details must not be exposed to the API client.
    assert "critical database failure" not in response.text

    cur.__exit__.assert_called_once()
    conn.__exit__.assert_called_once()

    assert conn.__exit__.call_args == cur.__exit__.call_args
    assert conn.__exit__.call_args.args[0] is psycopg.DatabaseError


def test_analytics_endpoint_returns_503_when_connection_fails():
    """Verify a connection failure returns the generic analytics response."""

    with patch.object(
        analytics,
        "get_db_connection",
        side_effect=psycopg.OperationalError("critical connection failure"),
    ) as mock_get_db_connection:
        response = client.get("/analytics/top-skills")

    assert response.status_code == 503
    assert response.json() == {"detail": "Analytics data is temporarily unavailable"}

    # Database details should not be exposed to the API client
    assert "critical connection failure" not in response.text

    mock_get_db_connection.assert_called_once_with()
