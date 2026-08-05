"""Apply multi-user PostgreSQL schema via psycopg (Alembic-compatible SQL)."""

from __future__ import annotations

import argparse
from pathlib import Path

SCHEMA_SQL = Path(__file__).resolve().parents[3] / "alembic" / "versions" / "20260801_0001_multiuser_schema.py"


def apply_schema(database_url: str) -> None:
    import psycopg

    # Extract SQL between SCHEMA = """ ... """
    text = (Path(__file__).resolve().parents[3] / "alembic" / "versions" / "20260801_0001_multiuser_schema.py").read_text(
        encoding="utf-8"
    )
    start = text.index('SCHEMA = """') + len('SCHEMA = """')
    end = text.index('"""', start)
    sql = text[start:end]
    with psycopg.connect(database_url) as conn:
        conn.execute(sql)
        conn.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply multi-user Postgres schema")
    parser.add_argument("--database-url", default="", help="PostgreSQL DATABASE_URL")
    args = parser.parse_args(argv)
    import os

    url = args.database_url or os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("DATABASE_URL is required")
    apply_schema(url)
    print("Multi-user schema applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
