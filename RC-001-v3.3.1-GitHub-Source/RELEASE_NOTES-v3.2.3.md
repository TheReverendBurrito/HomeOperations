# RC-001 v3.2.3 — Metadata Consistency

Build: `2026.07.17.005`

This maintenance release removes the stale hard-coded version from the Home Operations Center card. The card now renders its version and build directly from RC-001 release metadata, keeping it synchronized with the header, footer, and `/api/build` endpoint.

No alert thresholds, network behavior, integrations, or database schema changed.
