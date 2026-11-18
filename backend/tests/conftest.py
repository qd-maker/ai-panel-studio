import pytest
from sqlalchemy import Engine

from app.db import create_db_engine, init_db


@pytest.fixture
def engine(tmp_path) -> Engine:
    """每个测试一个独立的临时 SQLite 文件，已建表。"""
    eng = create_db_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    init_db(eng)
    yield eng
    eng.dispose()
