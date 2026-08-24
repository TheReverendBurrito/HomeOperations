# GitHub Sanitization Report

Source: `RC-001-v3.3.1-Home-Operations-Identity.zip`

## Removed or generalized

- Personal surname branding and named workstation fixtures
- Exact home-area coordinates and location labels
- Private subnet assignments and device-specific infrastructure addresses
- Site-specific WAN names and speeds
- Camera names and Home Assistant entity IDs
- Workstation-specific Homebrew executable paths
- Default notification delivery and location-dependent features

## Repository safeguards

- Expanded `.gitignore` for secrets, databases, logs, backups, build output, and
  private runtime data
- Rebuilt `.env.example` with blank secrets and documentation-only addresses
- Added security, contribution, and licensing guidance
- Added automated syntax, validation, privacy, and secret-pattern checks

## Publication note

The package is prepared for source publication, but the repository owner must
choose a license before granting public reuse rights. A final human review of
the GitHub diff and repository settings is still recommended before publishing.

## Validation result

- 15 release-structure and UI checks passed
- 4 Peplink session-reliability unit tests passed
- 19 route, API, topology, accessibility, performance, and installer checks passed
- Python, JavaScript, and shell syntax checks passed
- Targeted privacy and credential-pattern scans returned no findings
