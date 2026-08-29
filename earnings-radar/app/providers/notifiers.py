"""Push notification adapters: ntfy (default) and Pushover.

Both are dumb HTTP POSTs — high reliability, zero infrastructure, instant
iPhone delivery via their respective apps.
"""
from __future__ import annotations

import httpx

from app.config import get_settings
from app.providers.base import NotifierProvider, ProviderError


class NtfyNotifier(NotifierProvider):
    name = "ntfy"

    def __init__(self, client: httpx.Client | None = None,
                 server: str | None = None, topic: str | None = None):
        settings = get_settings()
        self._server = (server or settings.ntfy_server).rstrip("/")
        self._topic = topic if topic is not None else settings.ntfy_topic
        self._client = client or httpx.Client(timeout=10.0)

    def enabled(self) -> bool:
        return bool(self._topic)

    def send(self, title: str, body: str, high_priority: bool = False) -> None:
        if not self.enabled():
            return
        # JSON publish API: handles UTF-8/emoji titles, unlike raw headers.
        payload = {
            "topic": self._topic,
            "title": title,
            "message": body,
            "priority": 5 if high_priority else 4,
        }
        try:
            resp = self._client.post(self._server, json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"ntfy send failed: {exc}") from exc


class PushoverNotifier(NotifierProvider):
    name = "pushover"

    API_URL = "https://api.pushover.net/1/messages.json"

    def __init__(self, client: httpx.Client | None = None,
                 user_key: str | None = None, app_token: str | None = None):
        settings = get_settings()
        self._user_key = user_key if user_key is not None else settings.pushover_user_key
        self._app_token = app_token if app_token is not None else settings.pushover_app_token
        self._client = client or httpx.Client(timeout=10.0)

    def enabled(self) -> bool:
        return bool(self._user_key and self._app_token)

    def send(self, title: str, body: str, high_priority: bool = False) -> None:
        if not self.enabled():
            return
        payload = {
            "token": self._app_token,
            "user": self._user_key,
            "title": title,
            "message": body,
            "priority": 1 if high_priority else 0,
        }
        try:
            resp = self._client.post(self.API_URL, data=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"pushover send failed: {exc}") from exc
