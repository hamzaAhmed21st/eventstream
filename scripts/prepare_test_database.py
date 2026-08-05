#!/usr/bin/env python3
"""Create the isolated PostgreSQL test database when it does not exist."""

from __future__ import annotations

import argparse
import os
import time
from collections.abc import Sequence

import psycopg
from psycopg import sql
from sqlalchemy.engine import URL, make_url

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://eventstream:eventstream@localhost:5432/eventstream_test"
)


def parse_args(argv: Sequence[str] | None = None) -> str:
    parser = argparse.ArgumentParser(
        description="Create a missing PostgreSQL database whose name contains 'test'."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL),
        help="isolated SQLAlchemy PostgreSQL URL (default: TEST_DATABASE_URL or local test DB)",
    )
    return str(parser.parse_args(argv).database_url)


def validate_test_url(raw_url: str) -> URL:
    url = make_url(raw_url)
    if url.drivername != "postgresql+psycopg":
        raise ValueError("test database URL must use the postgresql+psycopg driver")
    if url.database is None or "test" not in url.database.lower():
        raise ValueError("test database name must contain 'test'")
    return url


def ensure_test_database(raw_url: str, *, attempts: int = 30) -> None:
    test_url = validate_test_url(raw_url)
    database_name = test_url.database
    assert database_name is not None
    admin_url = test_url.set(drivername="postgresql", database="postgres")
    admin_dsn = admin_url.render_as_string(hide_password=False)
    last_error: psycopg.OperationalError | None = None

    for attempt in range(1, attempts + 1):
        try:
            with psycopg.connect(admin_dsn, autocommit=True) as connection:
                exists = connection.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (database_name,),
                ).fetchone()
                if exists is None:
                    connection.execute(
                        sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
                    )
                    print(f"Created isolated test database {database_name!r}.")
                else:
                    print(f"Isolated test database {database_name!r} already exists.")
                return
        except psycopg.OperationalError as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(1)

    raise RuntimeError("PostgreSQL did not become ready for test database setup") from last_error


def main(argv: Sequence[str] | None = None) -> int:
    ensure_test_database(parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
