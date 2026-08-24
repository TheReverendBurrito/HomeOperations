# RC-001 Changelog

## RC-001 v3.3.1 — 2026-07-21

- Renamed the dashboard to Home Operations Center across page headers, browser titles, footer, service metadata, watchdog notifications, and Pushover links.
- Updated the header subtitle to Infrastructure · Environment · Security.
- Replaced the fixed five-camera Security coverage label with a count derived from the configured Ring camera inventory.
- Preserved the configured camera count during temporary Home Assistant or Ring outages.
- Preserved all v3.3.0 weather-radar and v3.2.5 Peplink session-reliability behavior.

## RC-001 v3.3.0 — 2026-07-21

- Added a responsive Local Weather Radar card to Environmental Operations.
- Embedded a Windy precipitation-radar layer centered on configured coordinates.
- Added native lazy loading so the radar does not delay dashboard status telemetry.
- Added a live-radar indicator, full-radar link, provider attribution, and isolated unavailable state.
- Added environment settings for enabling the radar and configuring latitude, longitude, and zoom.
- Preserved all v3.2.5 Peplink session-reliability behavior.

## RC-001 v3.2.5 — 2026-07-20

- Added automatic Peplink reauthentication after an expired API session.
- Serialized dashboard, alert-monitor, and networking-client API access through one shared session.
- Retried the original Peplink request once after successful reauthentication.
- Removed the independent client-discovery login/logout cycle that could invalidate the shared session.
- Added last-known-good WAN status fallback so a temporary Peplink API failure does not make `/api/status` return HTTP 500.
- Added explicit stale/error/last-success Peplink telemetry to `/api/status`.
- Added automated coverage for expired sessions, concurrent callers, request parameters, and stale WAN fallback.

## v3.0.0 — Production

- Promoted the validated Networking page to production.
- Updated application header and footer to Production v3.0.0.
- Froze Home, Environment, Security, Lighting, Networking, and Operations.
- Added production freeze metadata and release notes.
- Hardened deployment-side validation when Node.js is unavailable.

# Changelog

## 1.1.1

- Added read-only Peplink SNMPv2c polling through `snmp_monitor.py`.
- Added live per-WAN download and upload Mbps.
- Added current traffic-share bars for three configurable WAN connections.
- Added WAN Telemetry status to System Information.
- Preserved all RC-001 v1.1 behavior and integrations.

# Changelog

## RC-001 v1.1 — Operations Release

### Added
- Persistent WAN state timers and transition events
- Cabinet runtime display
- Four-part operations health strip
- Categorized event styling
- Animated banner status indicator
- System Information card
- System integration status fields in `/api/status`

### Changed
- Product branding standardized as Home Operations Center
- Footer version updated to RC-001 v1.1
- WLED update failures no longer prevent the rest of `/api/status` from rendering

### Preserved
- Peplink authentication and WAN parsing
- Home Assistant temperature and humidity retrieval
- Official Ookla Speedtest implementation
- Existing WLED preset mapping
- Manual lighting controls
# RC-001 v3.1.0 — 2026-07-17

- Added Pushover operational alert delivery.
- Added persistent, browser-independent alert monitoring.
- Added confirmed AQI advisory and critical thresholds.
- Added sustained Internet, Home Assistant, and camera outage rules.
- Added daily low-camera-battery reminders.
- Added an independent RC-001 systemd watchdog.
- Preserved the v3.0 dashboard and networking production baseline.
# RC-001 v3.2.0 — 2026-07-17

- Added durable Pushover delivery queueing and controlled retry backoff.
- Added delivery health, request identifiers, failures, and timestamps to `/api/alerts`.
- Added persistent AirNow last-known-good readings with Current, Delayed, and Stale states.
- Prevented delayed or cached AQI data from satisfying new alert confirmations.
- Replaced sequential Ring entity requests with one Home Assistant state snapshot.
- Added Alerting & Notification Health to the Operations page.
- Preserved all v3.1 alert thresholds, cooldowns, and recovery behavior.
# RC-001 v3.2.1 — 2026-07-17

- Replaced the obsolete Security `Scope / Phase 2` metric with `Coverage / 5 Cameras`.
- Updated the supporting description to `Perimeter and entry monitoring`.
- Preserved all v3.2.0 alert reliability and Operations functionality.

# RC-001 v3.2.2 — 2026-07-17

- Replaced the static T-Mobile `5G Standby` descriptor with live `5G Active Offload`, `5G Standby`, and `5G Unavailable` states.
- Made the Environmental Operations summary use the most severe cabinet or outdoor AQI condition.
- Added warning and critical indicator colors to the Environmental Operations home card.
- Preserved alert thresholds, outbound-policy telemetry, QoS behavior, and all v3.2.1 functionality.

# RC-001 v3.2.3 — 2026-07-17

- Replaced the stale Operations Center `v2.0 / Phase 3.2` text with live release metadata.
- The card now stays synchronized with `VERSION.json` and displays the current version and build.
- Preserved all v3.2.2 status-accuracy behavior.

# RC-001 v3.2.4 — 2026-07-17

- Constrained long Ookla server names to a centered two-line label inside the Test Server tile.
- Added a hover tooltip containing the complete server name.
- Preserved all v3.2.3 metadata and status-accuracy behavior.
