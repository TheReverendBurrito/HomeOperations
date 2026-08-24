from __future__ import annotations

import sys

from pushover_service import is_configured, send_notification


def main() -> int:
    if not is_configured():
        print("Pushover is not configured. Add PUSHOVER_USER_KEY and PUSHOVER_API_TOKEN to .env.")
        return 1
    ok, error = send_notification(
        "RC-001 — Test Notification",
        "Pushover alert delivery is configured correctly.",
    )
    if not ok:
        print(error or "Pushover test failed")
        return 1
    print("Pushover test notification sent successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
