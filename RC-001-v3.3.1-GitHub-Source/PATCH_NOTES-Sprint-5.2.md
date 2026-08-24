# RC-001 Sprint 5.2 — Startup Validation

This patch adds deterministic startup validation before background workers and Flask begin serving traffic.

## Fatal startup checks

- `.env` file exists
- Required project directories are writable
- SQLite database can be opened and written
- Peplink URL, username, and password are configured
- Home Assistant URL and token are configured

A fatal failure prevents startup and prints a clear diagnostic.

## Warning-only checks

- Home Assistant network reachability
- WLED reachability
- AirNow completeness
- Ookla Speedtest executable
- SNMP utility executable

Connectivity failures are warnings so a temporary LAN or cloud outage does not prevent RC-001 from starting.

## API

`GET /api/startup-validation` reruns the checks and returns JSON. It returns HTTP 200 when all required checks pass and HTTP 503 when a fatal check fails.

## Unchanged

No templates, CSS, JavaScript, camera mappings, thresholds, event policy, or database schema migrations are included.
