# RC-001 v2.1.0 Changelog

## Sprint 3 — Centralized Configuration

- Moved cabinet temperature and humidity warning/critical thresholds into `config.py` and `.env`.
- Moved AirNow history sampling, retention, and trend thresholds into configuration.
- Added startup validation for contradictory or non-positive operational thresholds.
- Preserved all existing default values, so dashboard behavior is unchanged unless `.env` overrides them.
- No templates, CSS, JavaScript, routes, camera mappings, or event-policy behavior were changed.

## Sprint 2 — Service Cleanup

- Added `home_assistant.py` as the single Home Assistant REST client and state-normalization layer.
- Refactored Ring and environmental telemetry to share one request implementation.
- Removed duplicate URL, authorization, availability, numeric, timestamp, and boolean parsing logic.
- Removed an unused legacy Ring state table initializer.
- Preserved the Boat motion-capability fallback and the Sprint 1 major-event transition engine.
- Added configurable `HOME_ASSISTANT_TIMEOUT_SECONDS` with a default of 10 seconds.
- No templates, CSS, JavaScript, routes, entity IDs, thresholds, or dashboard behavior were changed.

## Sprint 1 — Major Events

- Added persistent transition-state deduplication.
- Limited security logging to camera availability, battery severity, motion-detection posture, and integration availability transitions.
- Suppressed routine motion, doorbell activity, polling updates, and ordinary battery fluctuations.
- First observations establish a baseline without flooding the Operations Log.
