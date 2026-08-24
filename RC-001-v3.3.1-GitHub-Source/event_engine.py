from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Iterable

from database import DB_PATH


@dataclass(frozen=True)
class StateTransition:
    object_id: str
    category: str
    state: str
    event_id: str | None = None
    severity: str | None = None
    message: str | None = None
    emit_from: tuple[str, ...] | None = None


def ensure_state_table() -> None:
    """Create the persistent transition-state table used for deduplication."""
    with sqlite3.connect(DB_PATH) as conn:
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
        conn.commit()


def apply_transitions(
    transitions: Iterable[StateTransition],
    timestamp: int | None = None,
) -> list[StateTransition]:
    """Persist states and emit only genuine state-transition events.

    The first observation establishes a baseline and intentionally creates no
    event. Repeated polls in the same state are silent.
    """
    now = int(timestamp or time.time())
    emitted: list[StateTransition] = []
    ensure_state_table()

    with sqlite3.connect(DB_PATH) as conn:
        for item in transitions:
            row = conn.execute(
                "SELECT current_state, state_since FROM operational_state WHERE object_id = ?",
                (item.object_id,),
            ).fetchone()

            if row is None:
                conn.execute(
                    """
                    INSERT INTO operational_state (
                        object_id, category, current_state, previous_state,
                        state_since, last_transition, last_event_id,
                        last_event_severity, last_event_message
                    ) VALUES (?, ?, ?, NULL, ?, ?, NULL, NULL, NULL)
                    """,
                    (item.object_id, item.category, item.state, now, now),
                )
                continue

            previous_state, previous_since = row
            if previous_state == item.state:
                continue

            transition_allowed = item.emit_from is None or previous_state in item.emit_from
            event_id = item.event_id if item.message and transition_allowed else None
            severity = item.severity if item.message and transition_allowed else None
            message = item.message if item.message and transition_allowed else None

            conn.execute(
                """
                UPDATE operational_state
                SET category = ?, previous_state = ?, current_state = ?,
                    state_since = ?, last_transition = ?, last_event_id = ?,
                    last_event_severity = ?, last_event_message = ?
                WHERE object_id = ?
                """,
                (
                    item.category,
                    previous_state,
                    item.state,
                    now,
                    now,
                    event_id,
                    severity,
                    message,
                    item.object_id,
                ),
            )

            if message:
                conn.execute(
                    "INSERT INTO event_log (timestamp, event_type, event_text) VALUES (?, ?, ?)",
                    (now, item.category, message),
                )
                emitted.append(item)

        conn.commit()

    return emitted
