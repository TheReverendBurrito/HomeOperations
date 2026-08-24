# RC-001 v3.2.2 — Status Accuracy

Build: `2026.07.17.004`

This maintenance release corrects two home-dashboard status inconsistencies:

- USB T-Mobile now displays `5G Active Offload` while connected, `5G Standby` while on standby, and `5G Unavailable` while down.
- Environmental Operations now reports `Smoke Present` for AQI 101–150 and `Air Quality Alert` for AQI 151 or greater instead of showing `Optimal` based only on cabinet conditions.
- The Environmental Operations status indicator now follows the resulting good, warning, or critical state.

No alert thresholds, Peplink configuration, QoS rules, integrations, or database schema changed.
