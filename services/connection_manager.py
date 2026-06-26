# services/connection_manager.py
"""
ConnectionManager — Singleton pattern for database and cache connections.

WHY SINGLETON HERE
-------------------
A connection pool is expensive to create and must be shared across the
entire application lifetime. Creating a new pool per request would
exhaust available connections and destroy performance. The Singleton
pattern guarantees exactly ONE pool object exists per process, and
every request borrows a connection from that single pool.

TWO SINGLETONS
--------------
DatabaseManager  — wraps SQLAlchemy's connection pool for PostgreSQL.
                   SQLAlchemy already manages the pool internally;
                   the Singleton ensures we call create_engine() once.

CacheManager     — wraps a Redis client. redis-py's ConnectionPool is
                   also created once; the Singleton ensures we call
                   redis.from_url() once.

THREAD SAFETY NOTE
-------------------
Python's __new__ is NOT thread-safe by default. In a production async
server with multiple workers you would use a threading.Lock(). For a
single-process uvicorn deployment (our case) this is safe as-is because
the Singleton is initialised at startup in a single-threaded context
before any requests arrive.

ASYNC vs SYNC
--------------
We use psycopg2 (sync driver) with SQLAlchemy Core here because:
  1. The existing repositories use raw SQL strings — not async ORM
  2. FastAPI's BackgroundTasks run in a thread pool anyway
  3. Adding asyncpg would require rewriting all SQL with async context
     managers — a separate migration step

If you later want async, swap to:
  create_async_engine(...) + asyncpg driver
  and change get_db_connection() to an async context manager.
"""

import logging
import threading
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection

from config.settings import get_settings

logger = logging.getLogger(__name__)


# ==============================================================================
# DatabaseManager — Singleton for PostgreSQL connection pool
# ==============================================================================

class DatabaseManager:
    """
    Singleton that holds a single SQLAlchemy Engine (connection pool)
    for the entire application lifetime.

    Usage:
        db = DatabaseManager()          # always returns the same instance
        with db.get_connection() as conn:
            rows = conn.execute(text("SELECT 1"))

    WHY SQLAlchemy Core, not ORM
    ------------------------------
    The repositories use raw SQL strings. SQLAlchemy Core gives us:
      - Connection pooling (the main reason)
      - Dialect handling (RETURNING, ON CONFLICT syntax differences)
      - Parameter binding (:name style instead of ? for psycopg2)
    Without forcing us to rewrite everything as ORM models.
    """

    _instance: Optional["DatabaseManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "DatabaseManager":
        # Double-checked locking — safe for multi-threaded startup
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._engine = None
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def initialize(self, database_url: str) -> None:
        """
        Creates the connection pool. Called once at app startup.

        Separating __new__ from initialize() lets tests inject a
        test database URL before the pool is created.

        pool_size=10     — connections kept open permanently
        max_overflow=20  — extra connections allowed under load
        pool_pre_ping=True — test connections before use (detects
                             stale connections after Postgres restarts)
        """
        if self._initialized:
            logger.warning("DatabaseManager.initialize() called more than once — ignoring.")
            return

        if not database_url:
            raise ValueError(
                "DATABASE_URL is empty. "
                "Set it in .env or docker-compose environment."
            )

        self._engine: Engine = create_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,       # validates connections before handing out
            pool_recycle=1800,        # recycle connections every 30 min
                                      # prevents "server closed connection" errors
            echo=False,               # set True to log all SQL (dev only)
        )
        self._initialized = True
        logger.info(
            f"DatabaseManager: connection pool created. "
            f"pool_size=10, max_overflow=20"
        )

    @property
    def engine(self) -> Engine:
        if not self._initialized:
            raise RuntimeError(
                "DatabaseManager has not been initialised. "
                "Call DatabaseManager().initialize(database_url) at startup."
            )
        return self._engine

    @contextmanager
    def get_connection(self) -> Generator[Connection, None, None]:
        """
        Context manager that yields a SQLAlchemy Connection from the pool.

        The connection is automatically returned to the pool when the
        with-block exits (even on exception).

        Usage:
            db = DatabaseManager()
            with db.get_connection() as conn:
                result = conn.execute(text("SELECT 1"))

        WHY not a session (ORM):
            Sessions are for ORM unit-of-work patterns. We use Core
            connections because our repos write raw SQL.
        """
        with self.engine.connect() as connection:
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def dispose(self) -> None:
        """
        Closes all pooled connections. Call during app shutdown or in
        tests between test cases to avoid connection leaks.
        """
        if self._initialized and self._engine:
            self._engine.dispose()
            logger.info("DatabaseManager: connection pool disposed.")

    @classmethod
    def reset(cls) -> None:
        """
        Resets the Singleton. Used in tests only — never in production.
        Allows tests to create a fresh DatabaseManager with a test URL.
        """
        with cls._lock:
            if cls._instance and cls._instance._initialized:
                cls._instance.dispose()
            cls._instance = None


# ==============================================================================
# CacheManager — Singleton for Redis connection pool
# ==============================================================================

class CacheManager:
    """
    Singleton that holds a single Redis client (with its own internal
    connection pool) for the entire application lifetime.

    Usage:
        cache = CacheManager()
        cache.client.set("key", "value", ex=60)
        value = cache.client.get("key")

    WHY decode_responses=True:
        Returns str instead of bytes. Our code works with strings
        (JSON, progress events) — never raw bytes.

    CURRENT USES IN THIS PROJECT
    -----------------------------
    1. PROGRESS_STORE replacement — evaluation progress events
       (currently an in-memory dict; Redis survives server restart
        and works across multiple container instances)
    2. Rate limiting state (future — currently in-memory)
    3. Session tokens (future — currently localStorage)
    """

    _instance: Optional["CacheManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "CacheManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._client = None
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def initialize(self, redis_url: str) -> None:
        """
        Creates the Redis client and connection pool.
        Called once at app startup.

        redis-py's from_url() automatically creates a ConnectionPool
        internally — we don't need to manage the pool manually.
        """
        if self._initialized:
            logger.warning("CacheManager.initialize() called more than once — ignoring.")
            return

        if not redis_url:
            logger.warning(
                "CacheManager: REDIS_URL is empty. "
                "Redis features (progress tracking) will be unavailable. "
                "Set REDIS_URL in .env to enable."
            )
            self._initialized = True   # mark initialized so we don't re-attempt
            return

        try:
            import redis as redis_lib
            self._client = redis_lib.from_url(
                redis_url,
                decode_responses=True,  # always return str, not bytes
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            # Test the connection immediately so startup fails fast if Redis
            # is unreachable, rather than failing on the first request
            self._client.ping()
            self._initialized = True
            logger.info(f"CacheManager: connected to Redis at {redis_url}")

        except ImportError:
            logger.warning(
                "CacheManager: redis package not installed. "
                "Install it with: pdm add redis"
            )
            self._initialized = True

        except Exception as e:
            logger.error(
                f"CacheManager: failed to connect to Redis: {e}. "
                "Redis features will be unavailable."
            )
            self._initialized = True  # don't crash the app — degrade gracefully

    @property
    def client(self):
        """
        Returns the Redis client, or None if Redis is unavailable.

        Callers must handle None:
            cache = CacheManager()
            if cache.client:
                cache.client.set("key", "value")
        """
        if not self._initialized:
            raise RuntimeError(
                "CacheManager has not been initialised. "
                "Call CacheManager().initialize(redis_url) at startup."
            )
        return self._client

    @property
    def is_available(self) -> bool:
        """True if Redis is connected and usable."""
        return self._initialized and self._client is not None

    @classmethod
    def reset(cls) -> None:
        """Resets the Singleton. Tests only."""
        with cls._lock:
            if cls._instance and cls._instance._client:
                try:
                    cls._instance._client.close()
                except Exception:
                    pass
            cls._instance = None
