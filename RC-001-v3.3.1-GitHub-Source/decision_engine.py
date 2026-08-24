from __future__ import annotations

from typing import Any


def determine_lighting_status(wans: list[dict[str, Any]]) -> str:
    states = {wan["id"]: bool(wan.get("connected")) for wan in wans}
    work_up = states.get("1", False)
    home_up = states.get("2", False)
    tmobile_active = states.get("3", False)

    if work_up and home_up:
        return "normal"
    if tmobile_active:
        return "tmobile"
    if work_up or home_up:
        return "failover"
    return "offline"
