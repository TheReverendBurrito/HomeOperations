# RC-001 v3.3.0 — Environmental Awareness

Build: `2026.07.21.001`

This feature release adds local animated precipitation radar to the Environment page while preserving the established RC-001 interface and reliability behavior.

## Added

- Responsive Windy radar centered on configured coordinates.
- Live-radar status indicator and full-screen Windy link.
- Native browser lazy loading to avoid delaying RC-001 telemetry.
- A contained unavailable state that does not affect the rest of the dashboard.
- Configurable radar enablement, coordinates, and zoom through `.env`.

## Default Radar Configuration

- Latitude: configured with `WEATHER_RADAR_LATITUDE`
- Longitude: configured with `WEATHER_RADAR_LONGITUDE`
- Zoom: `8`
- Layer: animated precipitation radar

## Preserved

- Automatic Peplink session renewal and last-known-good WAN fallback from v3.2.5.
- Existing alert thresholds, Pushover delivery, and AQI behavior.
- Peplink outbound policies and QoS configuration.
- Database schema version 4.
