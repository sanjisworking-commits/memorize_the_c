"""Shared application-level PostgreSQL connection pool (hosted only)."""

from __future__ import annotations

from psycopg_pool import ConnectionPool

POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 5
POOL_OPEN_TIMEOUT_SECONDS = 15.0


def make_connection_pool(dsn: str) -> ConnectionPool:
    """Build a closed pool with default (tuple) row factory.

    Callers must ``open(wait=True)`` during app startup and ``close()`` on shutdown.
    Do not set ``row_factory`` on the pool or on borrowed connections.
    """
    return ConnectionPool(
        conninfo=dsn,
        min_size=POOL_MIN_SIZE,
        max_size=POOL_MAX_SIZE,
        open=False,
    )
