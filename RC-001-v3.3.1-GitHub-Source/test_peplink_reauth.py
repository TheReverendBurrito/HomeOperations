from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

import peplink


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class ExpiringSession:
    def __init__(self):
        self.authenticated = False
        self.get_count = 0
        self.login_count = 0
        self.last_params = None

    def post(self, *args, **kwargs):
        self.login_count += 1
        self.authenticated = True
        return FakeResponse({"stat": "ok"})

    def get(self, *args, **kwargs):
        self.get_count += 1
        self.last_params = kwargs.get("params")
        if not self.authenticated:
            return FakeResponse(
                {"stat": "fail", "code": 401, "message": "Unauthorized"}
            )
        return FakeResponse({"stat": "ok", "response": {"value": "ready"}})


class PeplinkReauthenticationTests(unittest.TestCase):
    def test_unauthorized_request_reauthenticates_and_retries_once(self):
        session = ExpiringSession()
        with patch.object(peplink, "SESSION", session), patch.dict(
            peplink.CONFIG, {"peplink_password": "configured"}
        ):
            result = peplink.get("/api/test")

        self.assertEqual(result, {"value": "ready"})
        self.assertEqual(session.login_count, 1)
        self.assertEqual(session.get_count, 2)

    def test_query_parameters_survive_reauthentication_retry(self):
        session = ExpiringSession()
        parameters = {"activeOnly": "no", "size": 1000}
        with patch.object(peplink, "SESSION", session), patch.dict(
            peplink.CONFIG, {"peplink_password": "configured"}
        ):
            peplink.get("/api/status.client", params=parameters)

        self.assertEqual(session.last_params, parameters)
        self.assertEqual(session.login_count, 1)

    def test_concurrent_callers_share_one_reauthentication(self):
        session = ExpiringSession()
        results = []
        failures = []

        def request():
            try:
                results.append(peplink.get("/api/test"))
            except Exception as exc:  # pragma: no cover - assertion records it
                failures.append(exc)

        with patch.object(peplink, "SESSION", session), patch.dict(
            peplink.CONFIG, {"peplink_password": "configured"}
        ):
            threads = [threading.Thread(target=request) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertFalse(failures)
        self.assertEqual(len(results), 4)
        self.assertEqual(session.login_count, 1)
        self.assertEqual(session.get_count, 5)

    def test_status_can_use_last_known_wan_snapshot(self):
        response = {
            "order": [1],
            "1": {
                "enable": True,
                "name": "WAN 1",
                "statusLed": "green",
                "message": "Connected",
            },
        }
        with patch.object(peplink, "get", return_value=response):
            fresh = peplink.get_wan_status()
        with patch.object(peplink, "get", side_effect=peplink.PeplinkError("offline")):
            stale = peplink.get_wan_status(allow_stale=True)

        self.assertFalse(fresh[0]["status_stale"])
        self.assertTrue(stale[0]["status_stale"])
        self.assertEqual(stale[0]["status_error"], "offline")


if __name__ == "__main__":
    unittest.main()
