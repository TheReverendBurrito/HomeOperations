# RC-001 v3.1.0 — Operational Alerting

Build: `2026.07.17.001`

This release adds low-noise Pushover notifications to the frozen RC-001 v3.0.0 production baseline. No dashboard page layouts or existing operational semantics were changed.

## Initial alert scope

- Unhealthy AQI at 151 or above after two consecutive fresh AirNow readings.
- Extreme AQI at 201 or above after two consecutive fresh readings.
- Internet Offline after no usable WAN is detected for 60 seconds.
- Home Assistant Offline after five continuous minutes.
- RC-001 Service Down after three failed minutes, monitored by an independent systemd service.
- Camera Offline after ten continuous minutes.
- Camera Battery Low at 20 percent or below, limited to one reminder per camera per day.
- One recovery notification when each active condition clears.

## Operational behavior

- Monitoring runs without an open dashboard browser.
- Alert state is persisted in SQLite to prevent duplicates across restarts.
- Pushover credentials remain exclusively in `/opt/rc001/.env`.
- A complete Internet outage is recorded locally; delivery can occur only when a usable WAN returns. Real-time total-outage detection requires a future external monitor.
- Existing `.env` and database contents are preserved by the installer.
