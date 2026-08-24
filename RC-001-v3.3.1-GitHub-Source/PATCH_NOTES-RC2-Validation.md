# RC-001 v2.1.0 RC2 Validation

## Scope

- Verified deterministic device classification and registry overrides.
- Verified topology node and edge referential integrity.
- Verified Networking section order and five collapsible content sections.
- Verified Device Details drawer, live status animation controls, and reduced-motion support.
- Verified Home, Operations, Security, and Networking routes render successfully.
- Verified Home, Operations, Security, and base templates remain unchanged from the authoritative source.
- Verified Networking CSS changes are isolated and append-only.
- Measured isolated local render and API response performance.

## Corrective change

The topology builder now attaches the Security group to the Peplink node when Home Assistant is unavailable, preventing an orphaned topology edge.

## Validation result

- 19 checks passed
- 0 checks failed

Live discovery accuracy against the production Peplink and browser-level acceptance remain deployment-side checks and are performed with `validate_rc2.py` after installation.
