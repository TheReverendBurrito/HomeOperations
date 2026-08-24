from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from config import CONFIG
import runtime_state

DB_PATH = CONFIG["database"]

STATUS_MESSAGES = {
    "normal": "🟢 Cabinet returned to normal operation",
    "failover": "🟠 WAN failover detected",
    "tmobile": "🔵 USB T-Mobile became the active connection",
    "offline": "🔴 Internet connection lost",
    "maintenance": "⚪ Maintenance lighting enabled",
    "firmware": "🟣 Firmware update mode enabled",
    "network": "🔵 Network lighting mode enabled",
}


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS status_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                lighting_status TEXT,
                wan_json TEXT,
                temperature REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_text TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wan_state (
                wan_id TEXT PRIMARY KEY,
                wan_name TEXT NOT NULL,
                state TEXT NOT NULL,
                state_since INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS air_quality_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                aqi INTEGER NOT NULL,
                category TEXT NOT NULL,
                level TEXT NOT NULL,
                pollutant TEXT,
                reporting_area TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_air_quality_timestamp "
            "ON air_quality_log(timestamp)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS operational_state (
                object_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                current_state TEXT NOT NULL,
                previous_state TEXT,
                state_since INTEGER NOT NULL,
                last_transition INTEGER NOT NULL,
                last_event_id TEXT,
                last_event_severity TEXT,
                last_event_message TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_state (
                alert_id TEXT PRIMARY KEY,
                current_state TEXT NOT NULL,
                condition_since INTEGER,
                consecutive_count INTEGER NOT NULL DEFAULT 0,
                last_observation_key TEXT,
                active INTEGER NOT NULL DEFAULT 0,
                last_notified INTEGER,
                delivery_status TEXT NOT NULL DEFAULT 'none',
                pending_title TEXT,
                pending_message TEXT,
                pending_priority INTEGER,
                retry_count INTEGER NOT NULL DEFAULT 0,
                next_retry_at INTEGER,
                last_delivery_error TEXT,
                last_delivered_at INTEGER,
                last_delivery_request TEXT,
                updated_at INTEGER NOT NULL
            )
            """
        )
        existing_alert_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(alert_state)").fetchall()
        }
        alert_column_migrations = {
            "delivery_status": "TEXT NOT NULL DEFAULT 'none'",
            "pending_title": "TEXT",
            "pending_message": "TEXT",
            "pending_priority": "INTEGER",
            "retry_count": "INTEGER NOT NULL DEFAULT 0",
            "next_retry_at": "INTEGER",
            "last_delivery_error": "TEXT",
            "last_delivered_at": "INTEGER",
            "last_delivery_request": "TEXT",
        }
        for column_name, definition in alert_column_migrations.items():
            if column_name not in existing_alert_columns:
                conn.execute(
                    f"ALTER TABLE alert_state ADD COLUMN {column_name} {definition}"
                )
        conn.commit()


def log_event(event_type: str, event_text: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO event_log (timestamp, event_type, event_text) VALUES (?, ?, ?)",
            (int(time.time()), event_type, event_text),
        )
        conn.commit()


def _wan_state_name(wan: dict[str, Any]) -> str:
    if wan.get("connected"):
        return "connected"
    if wan.get("standby"):
        return "standby"
    return "down"


def _wan_transition_message(name: str, state: str) -> str:
    if state == "connected":
        return f"🟢 {name} connected"
    if state == "standby":
        return f"🟡 {name} entered standby"
    return f"🔴 {name} went down"


def add_wan_durations(
    wans: list[dict[str, Any]],
    timestamp: int | None = None,
) -> list[dict[str, Any]]:
    """Persist WAN state transitions and add duration fields to each WAN."""
    now = int(timestamp or time.time())
    enriched: list[dict[str, Any]] = []

    with sqlite3.connect(DB_PATH) as conn:
        for wan in wans:
            wan_id = str(wan.get("id", ""))
            wan_name = str(wan.get("name", f"WAN {wan_id}"))
            state = _wan_state_name(wan)

            row = conn.execute(
                "SELECT state, state_since FROM wan_state WHERE wan_id = ?",
                (wan_id,),
            ).fetchone()

            if row is None:
                state_since = now
                conn.execute(
                    """
                    INSERT INTO wan_state (wan_id, wan_name, state, state_since)
                    VALUES (?, ?, ?, ?)
                    """,
                    (wan_id, wan_name, state, state_since),
                )
            else:
                previous_state, previous_since = row
                state_since = int(previous_since)

                if previous_state != state:
                    state_since = now
                    conn.execute(
                        """
                        UPDATE wan_state
                        SET wan_name = ?, state = ?, state_since = ?
                        WHERE wan_id = ?
                        """,
                        (wan_name, state, state_since, wan_id),
                    )
                    conn.execute(
                        """
                        INSERT INTO event_log (timestamp, event_type, event_text)
                        VALUES (?, ?, ?)
                        """,
                        (now, "wan", _wan_transition_message(wan_name, state)),
                    )
                elif wan_name != wan.get("name"):
                    conn.execute(
                        "UPDATE wan_state SET wan_name = ? WHERE wan_id = ?",
                        (wan_name, wan_id),
                    )

            enriched_wan = dict(wan)
            enriched_wan["state"] = state
            enriched_wan["state_since"] = state_since
            enriched_wan["state_duration_seconds"] = max(0, now - state_since)
            enriched.append(enriched_wan)

        conn.commit()

    return enriched


def log_status(status: dict[str, Any]) -> None:
    current = status["lighting_status"]
    if current == runtime_state.LAST_LOGGED_STATUS:
        return

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO status_log (timestamp, lighting_status, wan_json, temperature)
            VALUES (?, ?, ?, ?)
            """,
            (
                int(time.time()),
                current,
                json.dumps(status["wans"]),
                status.get("temperature"),
            ),
        )
        conn.commit()

    runtime_state.LAST_LOGGED_STATUS = current



def log_air_quality(observation: dict[str, Any]) -> dict[str, Any]:
    if (
        not observation.get("available")
        or not observation.get("is_fresh", True)
        or observation.get("aqi") is None
    ):
        return {
            "stored": False,
            "category_changed": False,
            "previous_level": None,
        }

    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT timestamp, aqi, level "
            "FROM air_quality_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        previous_level = row[2] if row else None
        should_store = (
            row is None
            or int(row[1]) != int(observation["aqi"])
            or now - int(row[0]) >= CONFIG["airnow_history_store_seconds"]
        )
        if should_store:
            conn.execute(
                """
                INSERT INTO air_quality_log
                    (timestamp, aqi, category, level, pollutant, reporting_area)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    int(observation["aqi"]),
                    str(observation.get("category") or "Unknown"),
                    str(observation.get("level") or "unknown"),
                    observation.get("pollutant"),
                    observation.get("reporting_area"),
                ),
            )
            conn.execute(
                "DELETE FROM air_quality_log WHERE timestamp < ?",
                (now - CONFIG["airnow_history_retention_days"] * 86400,),
            )
            conn.commit()

    return {
        "stored": should_store,
        "category_changed": (
            previous_level is not None
            and previous_level != observation.get("level")
        ),
        "previous_level": previous_level,
    }


def get_air_quality_history(hours: int = 24) -> list[dict[str, Any]]:
    cutoff = int(time.time()) - max(1, hours) * 3600
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT timestamp, aqi, category, level, pollutant
            FROM air_quality_log
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (cutoff,),
        ).fetchall()
    return [
        {
            "timestamp": row[0],
            "aqi": row[1],
            "category": row[2],
            "level": row[3],
            "pollutant": row[4],
        }
        for row in rows
    ]


def air_quality_trend(history: list[dict[str, Any]]) -> str:
    if len(history) < 2:
        return "Stable"
    delta = history[-1]["aqi"] - history[max(0, len(history) - 6)]["aqi"]
    if delta >= CONFIG["airnow_trend_delta"]:
        return "Worsening"
    if delta <= -CONFIG["airnow_trend_delta"]:
        return "Improving"
    return "Stable"

def get_recent_logs(limit: int = 100) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    with sqlite3.connect(DB_PATH) as conn:
        status_rows = conn.execute(
            """
            SELECT timestamp, lighting_status, temperature
            FROM status_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        event_rows = conn.execute(
            """
            SELECT timestamp, event_type, event_text
            FROM event_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    for timestamp, lighting_status, temperature in status_rows:
        events.append(
            {
                "timestamp": timestamp,
                "event_type": "status",
                "lighting_status": lighting_status,
                "event": STATUS_MESSAGES.get(
                    lighting_status,
                    f"⚪ Cabinet status changed to {lighting_status}",
                ),
                "temperature": temperature,
            }
        )

    for timestamp, event_type, event_text in event_rows:
        events.append(
            {
                "timestamp": timestamp,
                "event_type": event_type,
                "lighting_status": None,
                "event": event_text,
                "temperature": None,
            }
        )

    events.sort(key=lambda event: event["timestamp"], reverse=True)
    return events[:limit]
