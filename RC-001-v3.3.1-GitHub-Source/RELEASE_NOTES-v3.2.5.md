# RC-001 v3.2.5 — Session Reliability

Build: `2026.07.20.001`

This maintenance release corrects the recurring dashboard outage caused by an expired Peplink API session.

## Corrected

- A Peplink `401 Unauthorized` response now triggers one thread-safe reauthentication and one retry of the original request.
- Dashboard polling, Internet alert checks, and Networking client discovery now share the same authenticated Peplink session.
- Networking discovery no longer creates and logs out a second API session that could invalidate dashboard authentication.
- If the router API remains temporarily unavailable after retrying, `/api/status` uses the last successful WAN snapshot and marks Peplink telemetry as delayed instead of returning HTTP 500.

## Preserved

- Alert thresholds and Pushover delivery behavior.
- Peplink outbound policies and QoS configuration.
- Speed-test scheduling and results.
- Home, Environment, Security, Lighting, Networking, and Operations layouts.
- Database schema version 4.
