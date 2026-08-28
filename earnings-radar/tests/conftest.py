from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///" + tempfile.mkstemp(suffix=".db")[1])
os.environ.setdefault("SEC_USER_AGENT", "Earnings Radar Tests (tests@example.com)")

from app.config import Settings
from app.db import session as db_session_module


@pytest.fixture
def settings() -> Settings:
    return Settings(database_url=os.environ["DATABASE_URL"])


@pytest.fixture
def db():
    """Fresh in-file SQLite database per test."""
    fd_path = tempfile.mkstemp(suffix=".db")[1]
    os.environ["DATABASE_URL"] = f"sqlite:///{fd_path}"
    from app.config import get_settings
    get_settings.cache_clear()
    db_session_module._engine = None
    db_session_module._SessionLocal = None
    db_session_module.init_db()
    yield db_session_module
    db_session_module._engine = None
    db_session_module._SessionLocal = None
    get_settings.cache_clear()
