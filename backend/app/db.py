"""SQLite 连接与建表。

建表以 backend/db/schema.sql 为唯一来源，不用 ORM 的 metadata.create_all，
避免出现 SQL 文件和 Python 模型两份表定义。
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, event

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = BACKEND_DIR / "db" / "schema.sql"
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "app.db"


def get_database_url() -> str:
    """数据库地址，可用环境变量 APS_DATABASE_URL 覆盖。"""
    return os.getenv("APS_DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")


def _ensure_parent_dir(url: str) -> None:
    prefix = "sqlite:///"
    if url.startswith(prefix) and ":memory:" not in url:
        Path(url[len(prefix):]).parent.mkdir(parents=True, exist_ok=True)


def create_db_engine(url: str | None = None) -> Engine:
    """创建引擎。每个新连接都开启外键约束和 WAL。"""
    url = url or get_database_url()
    _ensure_parent_dir(url)
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    """执行 schema.sql 建表。语句都带 IF NOT EXISTS，可重复调用。"""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    raw = engine.raw_connection()
    try:
        raw.driver_connection.executescript(sql)
        raw.commit()
    finally:
        raw.close()


_engine: Engine | None = None


def get_engine() -> Engine:
    """进程内共享的引擎。第一次调用时自动建表。"""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
        init_db(_engine)
    return _engine
