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


def literal_default(column) -> str | None:
    """A SQL literal for a column's Python-side default, or None.

    SQLAlchemy's ``default=`` is applied in Python on insert, so it never
    reaches the DDL. Adding a NOT NULL column needs a value for the rows that
    already exist, and this is where it comes from — the same value new rows
    would get, so old and new rows agree.
    """
    import json

    default = column.default
    if default is None:
        return None

    if getattr(default, "is_scalar", False):
        value = default.arg
    elif getattr(default, "is_callable", False):
        try:                                   # SQLAlchemy passes a context
            value = default.arg(None)
        except TypeError:
            try:
                value = default.arg()
            except Exception:                  # noqa: BLE001
                return None
        except Exception:                      # noqa: BLE001
            return None
    else:
        return None

    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, (dict, list)):
        return "'" + json.dumps(value).replace("'", "''") + "'"
    return None


def add_missing_columns(engine, metadata) -> list[str]:
    """Add columns that exist in the models but not yet in the database.

    `create_all` only creates missing *tables*, so a schema addition would
    otherwise break an existing database on the next insert — the INSERT names
    a column the table does not have.

    A nullable column is added directly. A NOT NULL column is added only when
    its Python-side default gives us a value for the existing rows; that value
    goes into the DDL so old rows match what new ones will get. Without a
    default there is no honest answer for the rows already there, so it is
    refused and logged — that genuinely needs a hand-written migration.

    It never drops, renames, retypes or backfills anything else.

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
            if column.primary_key:
                logger.warning(
                    "%s.%s is a missing primary key — needs a hand-written "
                    "migration; leaving the schema alone", table.name, column.name)
                continue

            default = literal_default(column)
            if not column.nullable and default is None:
                logger.warning(
                    "%s.%s is missing, is NOT NULL and has no default — there is "
                    "no correct value for existing rows; leaving the schema alone",
                    table.name, column.name)
                continue

            ddl = (f'ALTER TABLE {table.name} '
                   f'ADD COLUMN {column.name} {column.type.compile(engine.dialect)}')
            if default is not None:
                ddl += f" DEFAULT {default}"
            if not column.nullable:
                ddl += " NOT NULL"
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
