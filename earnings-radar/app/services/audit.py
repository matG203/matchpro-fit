"""AuditService — every pipeline decision becomes a timestamped row."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.models import AuditLog

logger = logging.getLogger("earnings_radar.audit")


class AuditService:
    def __init__(self, session: Session):
        self._session = session

    def log(self, actor: str, action: str, detail: str = "", *,
            event_id: int | None = None, release_id: int | None = None,
            level: str = "INFO") -> None:
        self._session.add(AuditLog(actor=actor, action=action, detail=detail,
                                   event_id=event_id, release_id=release_id, level=level))
        logger.log(logging.getLevelName(level) if isinstance(logging.getLevelName(level), int)
                   else logging.INFO, "%s %s %s", actor, action, detail)
