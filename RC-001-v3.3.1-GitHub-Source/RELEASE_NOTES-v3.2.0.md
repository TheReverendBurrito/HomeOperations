# RC-001 v3.2.0 — Alert Reliability

Build: `2026.07.17.002`

This release builds on RC-001 v3.1.0 Operational Alerting and implements four approved improvements without changing the selected alert thresholds.

## Durable notification delivery

- Failed Pushover deliveries remain queued in SQLite.
- Retry backoff progresses through 1, 5, 15, 30, and 60 minutes.
- Successful delivery records the Pushover request identifier and delivery time.
- Cleared conditions cancel undelivered stale notifications.
- Delivered alerts still receive one recovery notification.

## AirNow resilience

- The last successful AirNow observation is persisted locally.
- A request failure retains the last valid AQI instead of replacing it with Unavailable.
- Readings are labeled Current, Delayed, or Stale and include their age.
- AirNow performs up to three controlled request attempts.
- Delayed and stale readings remain visible but cannot trigger or escalate an AQI alert.

## Home Assistant and Ring efficiency

- RC-001 now retrieves the Home Assistant state registry once per Ring collection.
- All five camera status cards are derived from that single snapshot.
- Partial entity omissions remain isolated to the affected camera capability.

## Operations visibility

The Operations page now reports:

- Pushover delivery health and last successful delivery.
- Background alert-worker health.
- Independent watchdog heartbeat.
- Active conditions, pending timers, and queued deliveries.
- Compact active-alert details and an Alerts event filter.

Existing `.env`, SQLite data, Pushover credentials, and device registry contents are preserved during installation.
