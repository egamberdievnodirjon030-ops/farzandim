"""Ma'lumotlar bazasi ulanishi."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import event, inspect
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .models import Base


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        parsed = make_url(url)
        self.is_sqlite = parsed.get_backend_name() == "sqlite"
        kwargs: dict = {}
        if self.is_sqlite:
            database = parsed.database
            if database and database != ":memory:":
                Path(database).parent.mkdir(parents=True, exist_ok=True)
            kwargs["connect_args"] = {"timeout": 30}
        else:
            kwargs.update(pool_size=10, max_overflow=20, pool_pre_ping=True)
        self.engine: AsyncEngine = create_async_engine(url, **kwargs)
        if self.is_sqlite:
            event.listen(self.engine.sync_engine, "connect", _sqlite_pragmas)
        self._sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_all(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_add_missing_columns)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Tranzaksiya: muvaffaqiyatli tugasa commit, xatoda rollback."""
        async with self._sessionmaker() as session, session.begin():
            yield session

    async def close(self) -> None:
        await self.engine.dispose()


def _add_missing_columns(sync_conn) -> None:
    """Yangi versiyada qo'shilgan ustunlarni mavjud bazaga qo'shadi (ma'lumot yo'qolmaydi)."""
    inspector = inspect(sync_conn)
    dialect = sync_conn.dialect
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            ddl = f'ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type.compile(dialect=dialect)}'
            if column.server_default is not None:
                default = column.server_default.arg
                default_sql = default.compile(dialect=dialect) if hasattr(default, "compile") else f"'{default}'"
                ddl += f" DEFAULT {default_sql} NOT NULL"
            sync_conn.exec_driver_sql(ddl)


def _sqlite_pragmas(dbapi_connection, _record) -> None:  # pragma: no cover - driver specific
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


__all__ = ["Database"]
