# Security Policy

## Supported version

Security fixes target the current sanitized RC-001 v3.3.1 source edition.

## Reporting

Do not open a public issue containing credentials, private addresses, camera
entity IDs, network inventories, logs, or screenshots. Report vulnerabilities
privately to the repository owner and include only the minimum reproduction
information needed.

## Deployment guidance

- Keep RC-001 on a trusted management network; do not expose port 5050 directly
  to the public internet.
- Store secrets only in `.env` with restrictive file permissions.
- Use a read-only SNMP community and least-privilege service accounts.
- Restrict router, Home Assistant, WLED, and camera access with firewall rules.
- Keep Raspberry Pi OS and Python dependencies patched.
- Rotate credentials immediately if they are disclosed.
