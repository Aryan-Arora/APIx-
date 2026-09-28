"""Configuration, authentication, bounded rate limiting and read-only access."""

import os
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from .mock_data import build_mock


@dataclass(frozen=True)
class Settings:
    use_mock: bool = False
    database_url: str = ""
    api_keys: tuple[str, ...] = ()
    allowed_origins: tuple[str, ...] = ("http://localhost:3000",)
    rate_limit: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        """Load explicit environment settings; never silently enable mock mode."""
        return cls(
            use_mock=os.getenv("USE_MOCK") == "1",
            database_url=os.getenv("DATABASE_URL", ""),
            api_keys=tuple(
                k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()
            ),
            allowed_origins=tuple(
                x.strip()
                for x in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(
                    ","
                )
                if x.strip()
            ),
        )


class Store:
    """SELECT-only repository; production startup never creates or seeds tables."""

    def __init__(self, settings: Settings):
        self.mock = build_mock() if settings.use_mock else None
        self.engine = None
        if not settings.use_mock and settings.database_url:
            url = settings.database_url
            if url.startswith(("postgres://", "postgresql://")):
                url = "postgresql+psycopg://" + url.split("://", 1)[1]
            kwargs = {"pool_pre_ping": True}
            if url.startswith("sqlite:"):
                kwargs["connect_args"] = {"check_same_thread": False}
                if ":memory:" in url:
                    kwargs["poolclass"] = StaticPool
            else:
                kwargs.update(
                    pool_size=3, max_overflow=2, connect_args={"connect_timeout": 10}
                )
            self.engine = create_engine(url, **kwargs)

    def query(self, sql: str, params: dict | None = None) -> list[dict]:
        """Execute a parameter-bound SELECT through a short-lived connection."""
        if self.engine is None:
            raise HTTPException(503, "Database is not configured")
        with self.engine.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(text(sql), params or {}).mappings()
            ]

    def rows(self, table: str) -> list[dict]:
        """Return a small metadata table; names come only from this allowlist."""
        if table not in {
            "routes",
            "scrape_runs",
            "backtest_results",
            "backtest_summary",
        }:
            raise ValueError("Unsupported metadata table")
        if self.mock is not None:
            return self.mock[table]
        return self.query(f"SELECT * FROM {table}")


class RateLimiter:
    def __init__(self, limit: int):
        self.limit = limit
        self.entries = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key: str) -> None:
        """Enforce a per-process rolling minute, pruning inactive clients."""
        now = time.monotonic()
        with self.lock:
            for client in list(self.entries):
                if not self.entries[client] or self.entries[client][-1] <= now - 60:
                    del self.entries[client]
            queue = self.entries[key]
            while queue and queue[0] <= now - 60:
                queue.popleft()
            if len(queue) >= self.limit:
                raise HTTPException(
                    429,
                    "Rate limit exceeded; retry in one minute",
                    headers={"Retry-After": "60"},
                )
            queue.append(now)


key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def authorize(request: Request, key: str | None = Security(key_header)) -> None:
    """Require a configured key; the browser demo key grants read access only."""
    settings = request.app.state.settings
    if not settings.api_keys:
        raise HTTPException(503, "API keys are not configured")
    if key is None or not any(
        secrets.compare_digest(key, expected) for expected in settings.api_keys
    ):
        raise HTTPException(401, "Missing or invalid X-API-Key")


def get_store(request: Request) -> Store:
    """Resolve the application-local repository."""
    return request.app.state.store
