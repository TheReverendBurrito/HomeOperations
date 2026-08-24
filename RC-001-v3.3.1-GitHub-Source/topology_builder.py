from __future__ import annotations

from collections import defaultdict
from typing import Any


def _safe_status(value: str | None) -> str:
    allowed = {"online", "offline", "configured", "warning", "critical"}
    return value if value in allowed else "configured"


def _device_node(
    device: dict[str, Any],
    *,
    node_type: str,
    parent_id: str | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": str(device.get("id") or device.get("name") or node_type),
        "label": str(device.get("name") or "Unnamed device"),
        "type": node_type,
        "status": _safe_status(device.get("status")),
        "status_label": str(device.get("status_label") or "Configured"),
        "parent_id": parent_id,
        "metrics": metrics or {},
        "address": device.get("address") or device.get("ip"),
        "connection": device.get("connection"),
    }


def build_topology(
    *,
    infrastructure: list[dict[str, Any]],
    security: list[dict[str, Any]],
    clients: list[dict[str, Any]],
    wan_names: list[str] | None = None,
) -> dict[str, Any]:
    wan_names = wan_names or ["Work DSL", "Home DSL", "T-Mobile"]

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    nodes.append(
        {
            "id": "internet",
            "label": "Internet Sources",
            "type": "root",
            "status": "configured",
            "status_label": "Configured",
            "parent_id": None,
            "metrics": {"wan_count": len(wan_names)},
            "address": None,
            "connection": None,
        }
    )

    for index, name in enumerate(wan_names, start=1):
        wan_id = f"wan_{index}"
        nodes.append(
            {
                "id": wan_id,
                "label": name,
                "type": "wan",
                "status": "configured",
                "status_label": "Configured",
                "parent_id": "internet",
                "metrics": {},
                "address": None,
                "connection": "WAN",
            }
        )
        edges.append({"source": "internet", "target": wan_id})

    infrastructure_by_id = {
        str(item.get("id")): item
        for item in infrastructure
        if item.get("id")
    }

    peplink = infrastructure_by_id.get("peplink") or {
        "id": "peplink",
        "name": "Peplink B One",
        "status": "configured",
        "status_label": "Configured",
    }
    peplink_node = _device_node(
        peplink,
        node_type="router",
        parent_id="internet",
        metrics={
            "wan_count": len(wan_names),
            "client_count": len(clients),
            "active_clients": sum(bool(item.get("active")) for item in clients),
        },
    )
    nodes.append(peplink_node)
    edges.append({"source": "internet", "target": peplink_node["id"]})

    deco = infrastructure_by_id.get("deco_mesh") or {
        "id": "deco_mesh",
        "name": "TP-Link Deco Mesh",
        "status": "configured",
        "status_label": "Configured",
    }
    wireless_clients = [
        item
        for item in clients
        if str(item.get("connection_type") or item.get("connection") or "").lower()
        in {"wifi", "wireless", "wi-fi"}
    ]
    deco_node = _device_node(
        deco,
        node_type="mesh",
        parent_id=peplink_node["id"],
        metrics={
            "ap_count": 3,
            "wireless_clients": len(wireless_clients),
        },
    )
    nodes.append(deco_node)
    edges.append({"source": peplink_node["id"], "target": deco_node["id"]})

    relationship_overrides = {
        "rc001": peplink_node["id"],
        "home_assistant": peplink_node["id"],
        "wled": deco_node["id"],
        "ac_infinity": "home_assistant",
    }

    for device in infrastructure:
        device_id = str(device.get("id") or "")
        if device_id in {"peplink", "deco_mesh"}:
            continue
        parent_id = relationship_overrides.get(device_id, peplink_node["id"])
        node = _device_node(
            device,
            node_type="infrastructure",
            parent_id=parent_id,
            metrics={},
        )
        nodes.append(node)
        edges.append({"source": parent_id, "target": node["id"]})

    security_parent_id = "home_assistant" if "home_assistant" in {node["id"] for node in nodes} else peplink_node["id"]

    security_group = {
        "id": "security_group",
        "label": "Security",
        "type": "group",
        "status": (
            "critical"
            if any(item.get("health") == "critical" for item in security)
            else "warning"
            if any(item.get("health") == "warning" for item in security)
            else "online"
        ),
        "status_label": "Camera Fleet",
        "parent_id": security_parent_id,
        "metrics": {
            "camera_count": len(security),
            "online": sum(item.get("status") == "online" for item in security),
            "alerts": sum(bool(item.get("issues")) for item in security),
        },
        "address": None,
        "connection": "Home Assistant",
    }
    nodes.append(security_group)
    edges.append({"source": security_parent_id, "target": "security_group"})

    for camera in security:
        node = _device_node(
            camera,
            node_type="security",
            parent_id="security_group",
            metrics={
                "battery_percent": camera.get("battery_percent"),
                "motion_enabled": camera.get("motion_enabled"),
            },
        )
        nodes.append(node)
        edges.append({"source": "security_group", "target": node["id"]})

    category_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for client in clients:
        category_groups[str(client.get("category") or "unknown")].append(client)

    client_group = {
        "id": "client_group",
        "label": "Clients",
        "type": "group",
        "status": "online" if any(item.get("status") == "online" for item in clients) else "configured",
        "status_label": "Client Inventory",
        "parent_id": deco_node["id"],
        "metrics": {
            "client_count": len(clients),
            "active": sum(bool(item.get("active")) for item in clients),
            "unknown": sum(item.get("category") == "unknown" for item in clients),
        },
        "address": None,
        "connection": "Peplink Inventory",
    }
    nodes.append(client_group)
    edges.append({"source": deco_node["id"], "target": "client_group"})

    for category, members in sorted(category_groups.items()):
        group_id = f"category_{category}"
        group_node = {
            "id": group_id,
            "label": members[0].get("category_label") or category.title(),
            "type": "category",
            "status": "online" if any(item.get("status") == "online" for item in members) else "offline",
            "status_label": f"{len(members)} devices",
            "parent_id": "client_group",
            "metrics": {
                "device_count": len(members),
                "active": sum(bool(item.get("active")) for item in members),
                "new": sum(bool(item.get("is_new")) for item in members),
            },
            "address": None,
            "connection": None,
        }
        nodes.append(group_node)
        edges.append({"source": "client_group", "target": group_id})

    children: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        children[edge["source"]].append(edge["target"])

    return {
        "root_id": "internet",
        "nodes": nodes,
        "edges": edges,
        "children": dict(children),
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "infrastructure_nodes": sum(
                node["type"] in {"router", "mesh", "infrastructure"}
                for node in nodes
            ),
            "security_nodes": sum(node["type"] == "security" for node in nodes),
            "client_categories": sum(node["type"] == "category" for node in nodes),
        },
    }
