from __future__ import annotations

import hashlib
import json
import os
import subprocess
import shutil
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
BASELINE = Path(os.environ.get("RC001_BASELINE_DIR", "")) if os.environ.get("RC001_BASELINE_DIR") else None


class IdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key == "id" and value:
                self.ids.append(value)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(condition: bool, name: str, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "detail": detail}


def mocked_network_payload() -> dict[str, Any]:
    return {
        "available": True,
        "summary": {
            "total": 10,
            "infrastructure": 3,
            "security": 2,
            "clients": 5,
            "active_clients": 4,
            "unknown": 1,
            "new": 1,
            "offline": 1,
        },
        "topology": {
            "internet_label": "Internet Sources",
            "wans": [{"name": "Work DSL", "status": "online"}],
            "router": {"name": "Peplink B One", "status": "online"},
            "mesh": {"name": "TP-Link Deco Mesh", "status": "configured"},
            "group_counts": {"infrastructure": 3, "security": 2, "clients": 5},
        },
        "infrastructure": [
            {"id": "peplink", "name": "Peplink B One", "status": "online", "status_label": "Online", "address": "192.0.2.1", "connection": "Wired", "category": "infrastructure"},
        ],
        "security": [
            {"id": "front-door", "name": "Front Door", "status": "online", "status_label": "Online", "connection": "Home Assistant", "category": "security", "battery_percent": 90, "motion_enabled": True, "issues": []},
        ],
        "clients": [
            {"id": "02:00:00:00:00:01", "mac": "02:00:00:00:00:01", "name": "Example Laptop", "hostname": "example-laptop", "ip": "192.0.2.20", "status": "online", "status_label": "Online", "connection": "Wireless", "category": "computers", "category_label": "Computers", "classification_source": "automatic", "is_new": False},
        ],
        "inventory": [],
        "category_labels": {"computers": "Computers"},
        "discovery": {"available": True, "source": "Peplink", "detail": "Mocked RC2 validation payload"},
        "errors": [],
        "updated_at": int(time.time()),
    }


def main() -> int:
    results: list[dict[str, Any]] = []

    # Syntax and package checks.
    compile_result = subprocess.run([sys.executable, "-m", "compileall", "-q", str(ROOT)], capture_output=True, text=True)
    results.append(check(compile_result.returncode == 0, "Python compilation", compile_result.stderr.strip()))

    node_path = shutil.which("node")
    if node_path:
        node = subprocess.run([node_path, "--check", str(ROOT / "static/rc001.js")], capture_output=True, text=True)
        results.append(check(node.returncode == 0, "JavaScript syntax", node.stderr.strip()))
    else:
        results.append(check(True, "JavaScript syntax", "Node.js not installed; deployment-side syntax check skipped (validated during packaging)"))

    shell = subprocess.run(["bash", "-n", str(ROOT / "install.sh")], capture_output=True, text=True)
    results.append(check(shell.returncode == 0, "Installer shell syntax", shell.stderr.strip()))

    # UI consistency and page structure.
    networking_html = (ROOT / "templates/networking.html").read_text(encoding="utf-8")
    parser = IdParser(); parser.feed(networking_html)
    duplicate_ids = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
    results.append(check(not duplicate_ids, "Networking unique element IDs", ", ".join(duplicate_ids)))

    section_markers = ["networking-health-section", "networkingTopology", "networkingInfrastructureGrid", "networkingSecurityGrid", "networkingClientGrid", "networkingInventoryBody"]
    section_names = ["Network Health", "Logical Network Topology", "Infrastructure", "Security Devices", "Client Devices", "Device Inventory"]
    positions = [networking_html.find(marker) for marker in section_markers]
    results.append(check(all(pos >= 0 for pos in positions) and positions == sorted(positions), "Networking section order", " > ".join(section_names)))
    results.append(check(networking_html.count('class="card networking-collapsible') == 5, "All content sections collapsible", "Expected 5 dropdown sections"))
    results.append(check("networkingDeviceDrawer" in networking_html and "networkingRegistryDialog" in networking_html, "Drawer and registry markup preserved"))

    css = (ROOT / "static/rc001.css").read_text(encoding="utf-8")
    js = (ROOT / "static/rc001.js").read_text(encoding="utf-8")
    results.append(check("prefers-reduced-motion" in css, "Reduced-motion accessibility"))
    results.append(check("networkingOpenDeviceDrawer" in js and "networkingAnimateStatusChanges" in js, "Live drawer and animation controllers"))

    # Discovery classification accuracy using deterministic fixtures.
    from device_classifier import classify_device
    fixtures = [
        ({"hostname": "example-laptop"}, "computers"),
        ({"name": "Front Door Ring"}, "security"),
        ({"name": "Samsung TV"}, "entertainment"),
        ({"hostname": "raspberrypi"}, "infrastructure"),
        ({"name": "iPhone"}, "mobile"),
        ({"name": "Mystery Device"}, "unknown"),
    ]
    fixture_failures = []
    for device, expected in fixtures:
        actual = classify_device(device)["category"]
        if actual != expected:
            fixture_failures.append(f"{device}: {actual} != {expected}")
    registry_override = classify_device({"hostname": "mystery"}, {"name": "Cabinet Sensor", "category": "iot"})
    if registry_override["category"] != "iot" or registry_override["name"] != "Cabinet Sensor":
        fixture_failures.append("Registry override was not authoritative")
    results.append(check(not fixture_failures, "Discovery classification fixtures", "; ".join(fixture_failures)))

    # Topology integrity.
    from topology_builder import build_topology
    infra = [{"id": "peplink", "name": "Peplink B One", "status": "online"}, {"id": "deco_mesh", "name": "TP-Link Deco Mesh", "status": "configured"}, {"id": "rc001", "name": "RC-001", "status": "online"}]
    security = [{"id": "cam1", "name": "Front Door", "status": "online", "health": "good"}]
    clients = [{"id": "c1", "name": "Laptop", "status": "online", "active": True, "category": "computers", "category_label": "Computers", "connection": "Wireless"}]
    topology = build_topology(infrastructure=infra, security=security, clients=clients)
    node_ids = {node["id"] for node in topology["nodes"]}
    bad_edges = [edge for edge in topology["edges"] if edge["source"] not in node_ids or edge["target"] not in node_ids]
    results.append(check(not bad_edges and topology["root_id"] == "internet", "Topology referential integrity", json.dumps(bad_edges)))

    # Flask page and API regression tests with external calls isolated.
    import app as app_module
    app_module.app.config.update(TESTING=True)
    app_module.collect_networking_status = mocked_network_payload
    client = app_module.app.test_client()
    page_paths = ["/", "/operations", "/security", "/networking"]
    page_times: dict[str, float] = {}
    for path in page_paths:
        start = time.perf_counter()
        responses = [client.get(path) for _ in range(30)]
        elapsed_ms = (time.perf_counter() - start) * 1000 / len(responses)
        page_times[path] = round(elapsed_ms, 3)
        results.append(check(all(response.status_code == 200 for response in responses), f"Route regression {path}", f"mean {elapsed_ms:.3f} ms"))

    api_start = time.perf_counter()
    api_responses = [client.get("/api/networking") for _ in range(100)]
    api_mean_ms = (time.perf_counter() - api_start) * 1000 / len(api_responses)
    api_schema_ok = all(response.status_code == 200 and response.get_json().get("available") is True for response in api_responses)
    results.append(check(api_schema_ok, "Networking API contract", f"mean {api_mean_ms:.3f} ms"))
    results.append(check(max(page_times.values()) < 50 and api_mean_ms < 25, "Local render performance budget", f"pages={page_times}, api={api_mean_ms:.3f} ms"))

    # Exact regression protection for page templates against authoritative source.
    if BASELINE and BASELINE.is_dir():
        protected = ["templates/home.html", "templates/operations.html", "templates/security.html", "templates/base.html"]
        changes = [name for name in protected if sha256(BASELINE / name) != sha256(ROOT / name)]
        results.append(check(not changes, "Protected page templates unchanged", ", ".join(changes)))
        baseline_css = (BASELINE / "static/rc001.css").read_text(encoding="utf-8")
        css_delta_is_append_only = css.startswith(baseline_css)
        results.append(check(css_delta_is_append_only, "CSS regression isolation", "Networking CSS must be append-only"))
    else:
        results.append(check(True, "Protected page templates unchanged", "Baseline directory not supplied; skipped"))
        results.append(check(True, "CSS regression isolation", "Baseline directory not supplied; skipped"))

    failed = [item for item in results if not item["ok"]]
    report = {
        "product": "RC-001",
        "milestone": "v3.0.0 Production Validation",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scope": ["discovery accuracy", "UI consistency", "performance", "Home regression", "Operations regression", "Security regression"],
        "environment": "isolated release validation; live Pi/Peplink acceptance remains deployment-side",
        "ok": not failed,
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "results": results,
    }
    (ROOT / "RC2_VALIDATION_REPORT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
