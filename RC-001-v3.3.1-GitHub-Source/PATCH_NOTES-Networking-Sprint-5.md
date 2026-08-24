# RC-001 v2.1.0 RC2 — Networking Sprint 5

- Added an accessible slide-out Device Details drawer for infrastructure, security, client, inventory, and topology nodes.
- Added live online pulse indicators and animated state-change acknowledgement.
- Added keyboard operation, Escape-to-close, backdrop close, focus treatment, and reduced-motion support.
- Preserved Home, Operations, Security, registry, discovery, filters, and topology behavior.

## Deployment corrections

- Added a production installer targeting `/opt/rc001`.
- Installer preserves `.env`, the runtime `data` directory, and the existing virtual environment lifecycle.
- Installer writes the correct `rc001.service`, performs a health check, and rolls back on service-start failure.
- Removed editor swap files, duplicate static copies, and embedded `.env` secrets from the release archive.
- Corrected the missing Flask `request` import required by device-registry update endpoints.

## Sprint 5.1 layout refinement

- Moved Network Health above Logical Network Topology.
- Converted Logical Network Topology, Infrastructure, Security Devices, and Client Devices into collapsed, accessible disclosure sections.
- Preserved device drawer, live status animations, inventory controls, discovery, and registry behavior.


## Sprint 5.2 layout refinement

- Converted Device Inventory into the same collapsed disclosure pattern used by the other Networking sections.
- Preserved inventory count, search, category/status/connection filters, sorting, registry editing, device drawer selection, and live refresh behavior.
