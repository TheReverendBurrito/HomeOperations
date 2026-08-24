# RC-001 v3.3.1 — Home Operations Identity

Build: `2026.07.21.002`

This release adopts **Home Operations Center** as the dashboard's product identity and prepares the Security summary for future camera expansion.

## Changes

- Updated the visible header, footer, page titles, installation service description, watchdog text, Pushover link title, and release metadata.
- Replaced the fixed Security coverage value with the number of cameras configured in RC-001.
- Retains that configured total when the live Home Assistant / Ring request is temporarily unavailable.

## Preserved behavior

- Automatic Peplink session renewal and last-known-good WAN status fallback.
- Windy precipitation radar on the Environment page.
- Existing alerts, telemetry, lighting, networking, and camera monitoring behavior.
