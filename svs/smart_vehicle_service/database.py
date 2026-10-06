"""PostgreSQL connection helpers for Smart Vehicle Service Management System."""

import os

import psycopg
from psycopg.rows import dict_row


def get_connection() -> psycopg.Connection:
    """Open a PostgreSQL connection using environment-based credentials."""
    required = ("DB_HOST", "DB_USER", "DB_PASSWORD")
    missing = [name for name in required if name not in os.environ]
    if missing:
        raise RuntimeError(
            "Missing database configuration: "
            + ", ".join(missing)
            + ". Set these environment variables before starting Flask."
        )

    return psycopg.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.getenv("DB_NAME", "smart_vehicle_service"),
        row_factory=dict_row,
    )
