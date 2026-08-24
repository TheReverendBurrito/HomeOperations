from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from config import CONFIG


class HomeAssistantError(RuntimeError):
    """Raised when the configured Home Assistant instance cannot be queried."""


def _base_url() -> str:
    value = CONFIG.get("home_assistant_url")
    if not value:
        raise HomeAssistantError("Home Assistant URL is not configured")
    return str(value).rstrip("/")


def _headers() -> dict[str, str]:
    token = CONFIG.get("home_assistant_token")
    if not token:
        raise HomeAssistantError("Home Assistant token is not configured")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def check_health(*, timeout: float | None = None) -> tuple[bool, str | None]:
    """Return Home Assistant API availability without depending on an entity."""
    request_timeout = float(
        timeout if timeout is not None else CONFIG.get("home_assistant_timeout_seconds", 10)
    )
    try:
        response = requests.get(
            f"{_base_url()}/api/",
            headers=_headers(),
            timeout=request_timeout,
        )
        response.raise_for_status()
        return True, None
    except (HomeAssistantError, requests.RequestException) as exc:
        return False, str(exc)


def get_state(
    entity_id: str | None,
    *,
    timeout: float | None = None,
) -> dict[str, Any] | None:
    """Return one Home Assistant entity-state object.

    A missing entity ID or an HTTP 404 returns ``None``. Configuration,
    connectivity, authentication, and malformed-response failures raise
    ``HomeAssistantError`` so callers can choose whether to surface or suppress
    the failure.
    """
    if not entity_id:
        return None

    request_timeout = float(
        timeout
        if timeout is not None
        else CONFIG.get("home_assistant_timeout_seconds", 10)
    )

    try:
        response = requests.get(
            f"{_base_url()}/api/states/{entity_id}",
            headers=_headers(),
            timeout=request_timeout,
        )
    except requests.RequestException as exc:
        raise HomeAssistantError(f"Home Assistant unavailable: {exc}") from exc

    if response.status_code == 404:
        return None

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise HomeAssistantError(
            f"Home Assistant returned HTTP {response.status_code}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise HomeAssistantError("Home Assistant returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise HomeAssistantError("Home Assistant returned an invalid state payload")

    return payload


def get_states_snapshot(*, timeout: float | None = None) -> dict[str, dict[str, Any]]:
    """Fetch all Home Assistant entity states once and index by entity_id."""
    request_timeout = float(
        timeout if timeout is not None else CONFIG.get("home_assistant_timeout_seconds", 10)
    )
    try:
        response = requests.get(
            f"{_base_url()}/api/states",
            headers=_headers(),
            timeout=request_timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except (HomeAssistantError, requests.RequestException, ValueError) as exc:
        raise HomeAssistantError(f"Unable to retrieve Home Assistant states: {exc}") from exc
    if not isinstance(payload, list):
        raise HomeAssistantError("Home Assistant returned an invalid states payload")
    return {
        str(item["entity_id"]): item
        for item in payload
        if isinstance(item, dict) and item.get("entity_id")
    }


def is_available(state: dict[str, Any] | None) -> bool:
    return bool(
        state
        and str(state.get("state", "")).strip().lower()
        not in {"", "none", "unknown", "unavailable"}
    )


def numeric_value(state: dict[str, Any] | None) -> float | None:
    if not is_available(state):
        return None
    try:
        return float(state.get("state"))
    except (TypeError, ValueError):
        return None


def integer_value(state: dict[str, Any] | None) -> int | None:
    value = numeric_value(state)
    return None if value is None else int(round(value))


def timestamp_value(
    state: dict[str, Any] | None,
) -> tuple[str | None, int | None, dict[str, Any]]:
    if not state:
        return None, None, {}

    raw = state.get("state")
    attributes = state.get("attributes") or {}
    if not isinstance(attributes, dict):
        attributes = {}

    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None, None, attributes

    return str(raw), int(parsed.timestamp()), attributes


def boolean_state(state: dict[str, Any] | None) -> bool | None:
    """Normalize a Home Assistant on/off-style entity state."""
    if not is_available(state):
        return None

    normalized = str(state.get("state")).strip().lower()
    if normalized in {"on", "true", "enabled", "1", "yes"}:
        return True
    if normalized in {"off", "false", "disabled", "0", "no"}:
        return False
    return None


def boolean_attribute(
    state: dict[str, Any] | None,
    attribute_name: str,
) -> bool | None:
    """Normalize a boolean-like Home Assistant entity attribute."""
    if not state:
        return None

    attributes = state.get("attributes") or {}
    if not isinstance(attributes, dict):
        return None

    value = attributes.get(attribute_name)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "on", "enabled", "1", "yes"}:
            return True
        if normalized in {"false", "off", "disabled", "0", "no"}:
            return False
    return None
