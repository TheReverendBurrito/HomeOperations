# Sprint 5.3 Patch Notes

## Scope

Adds standalone release-management utilities only.

## Files added

- `selftest.py`
- `backup_release.py`

## Behavior

- No application routes or service startup behavior are changed.
- No frontend files are changed.
- No database migration is performed.
- Backup archives are created with mode `0600` because they can contain `.env` credentials.
- The SQLite database is copied through the SQLite backup API rather than copied while open.
