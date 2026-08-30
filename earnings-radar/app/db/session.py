from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger("earnings_radar.db")

_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        kwargs: dict = {"pool_pre_ping": True}
        if settings.database_url.startswith("sqlite"):
            kwargs = {"connect_args": {"check_same_thread": False}}
        _engine = create_engine(settings.database_url, **kwargs)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def init_db() -> None:
    # Imported for side effects: both modules register tables on the shared Base.
    from app.db import catalyst_models, models  # noqa: F401

    engine = get_engine()
    models.Base.metadata.create_all(engine)
    add_missing_columns(engine, models.Base.metadata)


def add_missing_columns(engine, metadata) -> list[str]:
    """Add nullable columns that exist in the models but not yet in the database.

    `create_all` only creates missing *tables*, so a schema addition would
    otherwise break an existing local database on the next insert. This handles
    the only migration shape this project actually uses — adding a nullable
    column — and deliberately refuses anything else: it never drops, renames,
    retypes or backfills. Anything beyond an additive change needs a real
    migration written by hand.

    Returns the names of the columns it added, for logging and tests.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    added: list[str] = []

    for table in metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        present = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            if not column.nullable or column.primary_key:
                logger.warning(
                    "%s.%s is missing and is not nullable — needs a hand-written "
                    "migration; leaving the schema alone", table.name, column.name)
                continue
            ddl = (f'ALTER TABLE {table.name} '
                   f'ADD COLUMN {column.name} {column.type.compile(engine.dialect)}')
            try:
                with engine.begin() as conn:
                    conn.execute(text(ddl))
                added.append(f"{table.name}.{column.name}")
            except SQLAlchemyError as exc:
                logger.error("could not add %s.%s: %s", table.name, column.name, exc)

    if added:
        logger.info("schema updated: added %s", ", ".join(added))
    return added


@contextmanager
def db_session() -> Iterator[Session]:
    get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
