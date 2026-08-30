"""Production entrypoint — for Railway, or any container host.

`uvicorn app.main:app` works fine locally, where a person is watching. A hosted
deployment is different: nobody sees the first thirty seconds of logs, and the
two ways this system goes quietly wrong both happen at exactly that moment.

  * **The port.** Railway assigns one via `$PORT` and routes only to that.
    Binding 8000 instead produces a container that starts, passes its own
    logs, and is unreachable.

  * **The database.** Container filesystems are wiped on every deploy. On
    SQLite that means each redeploy starts with an empty database — and since
    alert deduplication is a database row, the poller would re-detect the last
    hour of news and push every one of those alerts again. A phone full of
    repeats, from a system that looks like it is working.

Both are checked here, loudly, before the server starts.
"""
from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger("earnings_radar.entrypoint")

BANNER = "=" * 70


def ephemeral_database_warning(database_url: str) -> str:
    """Empty when the configuration is safe; otherwise what is wrong with it."""
    if not database_url.startswith("sqlite"):
        return ""
    # A SQLite file on a host that wipes its disk on deploy.
    if _looks_hosted():
        return (
            "DATABASE_URL is SQLite, but this looks like a hosted container, "
            "whose filesystem is erased on every deploy and restart. The "
            "database holds the alert-deduplication rows, so each restart "
            "would re-detect recent news and push the same alerts again. "
            "Add a Postgres database and set DATABASE_URL to its connection "
            "string.")
    return ""


def _looks_hosted() -> bool:
    """Railway, Render, Fly and Heroku all announce themselves in the
    environment. Being wrong here is cheap in both directions: a false positive
    prints a warning on a laptop, a false negative just stays silent."""
    markers = ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "RENDER",
               "FLY_APP_NAME", "DYNO", "KUBERNETES_SERVICE_HOST")
    return any(os.environ.get(m) for m in markers)


def main() -> int:
    import uvicorn

    from app.config import get_settings

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s")

    settings = get_settings()
    port = int(os.environ.get("PORT", "8000"))

    warning = ephemeral_database_warning(settings.database_url)
    if warning:
        logger.error(BANNER)
        logger.error("EPHEMERAL DATABASE — %s", warning)
        logger.error(BANNER)

    logger.info("Earnings Radar starting on port %d", port)
    logger.info("Catalyst sweep every %ds · price feed delay %.0fs · "
                "wire feeds %s",
                settings.catalyst_poll_seconds,
                settings.market_data_delay_seconds,
                "on" if settings.wire_feeds_enabled else "off")
    # Said out loud on every boot, because it is the one property of this
    # system nobody should have to go and check.
    logger.info("This process never submits an order. It detects, scores and "
                "notifies; every trade is placed by hand.")

    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
