"""Deployment plumbing.

Every failure guarded here happens in the first seconds of a hosted boot,
where nobody is watching the logs, and each one produces a container that
looks healthy from the outside.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.db.session import normalise_database_url
from app.entrypoint import ephemeral_database_warning

ROOT = Path(__file__).resolve().parents[1]


# ── DATABASE_URL from a hosting provider ─────────────────────────────────────


@pytest.mark.parametrize("given,expected", [
    # Railway, Heroku and Render all still hand out the `postgres://` alias
    # SQLAlchemy 2 removed. Left alone it kills the process at import time.
    ("postgres://u:p@host:5432/db", "postgresql+psycopg2://u:p@host:5432/db"),
    ("postgresql://u:p@host:5432/db", "postgresql+psycopg2://u:p@host:5432/db"),
    # Already explicit — unchanged.
    ("postgresql+psycopg2://u:p@host:5432/db", "postgresql+psycopg2://u:p@host:5432/db"),
    ("sqlite:///./radar.db", "sqlite:///./radar.db"),
])
def test_provider_database_urls_are_made_usable(given, expected):
    assert normalise_database_url(given) == expected


def test_a_password_containing_the_scheme_text_is_not_mangled():
    url = "postgres://user:postgres://@host:5432/db"
    assert normalise_database_url(url) == (
        "postgresql+psycopg2://user:postgres://@host:5432/db")


# ── the ephemeral-database trap ──────────────────────────────────────────────


def test_sqlite_on_a_hosted_container_is_called_out(monkeypatch):
    """The quiet one: a wiped database means the alert dedup rows are gone, so
    every redeploy re-pushes the last hour of alerts."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    warning = ephemeral_database_warning("sqlite:///./radar.db")

    assert "erased on every deploy" in warning
    assert "Postgres" in warning


def test_sqlite_on_a_laptop_is_fine(monkeypatch):
    for marker in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "RENDER",
                   "FLY_APP_NAME", "DYNO", "KUBERNETES_SERVICE_HOST"):
        monkeypatch.delenv(marker, raising=False)
    assert ephemeral_database_warning("sqlite:///./radar.db") == ""


def test_postgres_on_a_hosted_container_is_fine(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    assert ephemeral_database_warning("postgresql://u:p@host/db") == ""


# ── the deployment manifest ──────────────────────────────────────────────────


def test_railway_config_is_valid_json_and_points_at_real_things():
    config = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    deploy = config["deploy"]

    assert (ROOT / config["build"]["dockerfilePath"]).exists()
    # One replica, deliberately. Two would each run their own scheduler and
    # push every alert twice.
    assert deploy["numReplicas"] == 1
    assert deploy["restartPolicyType"] == "ALWAYS"
    assert deploy["healthcheckPath"] == "/api/health"


def test_the_healthcheck_path_actually_serves(db):
    from fastapi.testclient import TestClient

    from app.main import create_app

    config = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    path = config["deploy"]["healthcheckPath"]

    with TestClient(create_app(start_scheduler=False)) as client:
        assert client.get(path).status_code == 200


def test_the_dockerfile_does_not_hardcode_the_port_in_its_start_command():
    """Binding 8000 on a host that assigns $PORT yields a container that starts,
    logs nothing wrong, and is never routed to."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cmd = next(line for line in dockerfile.splitlines() if line.startswith("CMD"))

    assert "--port" not in cmd
    assert "app.entrypoint" in cmd


def test_the_start_command_railway_runs_is_importable():
    """railway.json names a module; a typo there fails only on deploy."""
    import importlib

    config = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    command = config["deploy"]["startCommand"].split()

    assert command[:2] == ["python", "-m"]
    assert importlib.util.find_spec(command[2]) is not None


def test_env_example_documents_every_wire_setting():
    """A setting nobody can find is a setting nobody sets."""
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for name in ("WIRE_FEEDS_ENABLED", "WIRE_USE_DEFAULT_FEEDS", "WIRE_FEED_URLS",
                 "WIRE_MAX_BODY_FETCHES"):
        assert name in example, f"{name} is not in .env.example"


# An Anthropic key is `sk-ant-` plus a long opaque string. Documentation that
# writes `sk-ant-...` is showing the shape, not leaking a key, so the pattern
# requires enough real key characters to tell the two apart.
_REAL_ANTHROPIC_KEY = re.compile(r"sk-ant-[A-Za-z0-9_-]{12,}")


_SCANNED_SUFFIXES = {".md", ".json", ".yml", ".yaml", ".toml", ".bat", ".example"}


def _files_to_scan():
    """Committed text files at the project root.

    `.env` and friends are deliberately excluded: they are gitignored, they are
    not committed, and they are the one place a real key is *supposed* to live.
    Reading them here would make a passing test depend on a developer's private
    file, and a failing one print a warning about a key that is exactly where it
    belongs.
    """
    for path in sorted(ROOT.glob("*")):
        if path.is_dir() or path.name.startswith(".env"):
            continue
        if path.suffix in _SCANNED_SUFFIXES or path.name == "Dockerfile":
            yield path


def test_no_committed_file_contains_a_real_key():
    """The standing rule, enforced rather than remembered."""
    scanned = list(_files_to_scan())
    # If the glob ever stops matching, this test would pass by scanning nothing.
    assert {"README.md", "DEPLOY.md", "railway.json", "Dockerfile"} <= {
        p.name for p in scanned}

    for path in scanned:
        # errors="replace" rather than strict: the job is to find keys, and a
        # file this cannot decode should not be able to skip the scan. Reading
        # without an explicit encoding used the platform default, which is
        # cp1252 on Windows — so this passed on Linux and crashed on the one
        # machine that matters.
        text = path.read_text(encoding="utf-8", errors="replace")
        assert _REAL_ANTHROPIC_KEY.search(text) is None, (
            f"{path.name} contains what looks like a real key")


def test_the_example_env_file_ships_with_every_value_blank():
    """`.env.example` is copied to `.env`; a value left in it would be a key
    someone published to their own repository by accident."""
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("#"):
            continue
        for key in ("ANTHROPIC_API_KEY", "POLYGON_API_KEY", "FMP_API_KEY",
                    "FINNHUB_API_KEY", "PUSHOVER_APP_TOKEN", "PUSHOVER_USER_KEY",
                    "NTFY_TOPIC", "BENZINGA_API_KEY"):
            if line.startswith(f"{key}="):
                value = line.split("=", 1)[1].strip().strip('"')
                assert value == "", f".env.example has a value set for {key}"
