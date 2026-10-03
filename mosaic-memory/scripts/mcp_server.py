"""Mosaic MCP server.

Uses MCP v2 and talks to Mosaic's local FastAPI API over loopback.
No cloud call is made by this process.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any

from mcp.server import MCPServer

API_BASE = os.getenv("MOSAIC_API_BASE", "http://127.0.0.1:8000/api/v1")
mcp = MCPServer(
    "Mosaic Memory",
    instructions=(
        "Mosaic is a local-first personal context server. Prefer evidence-backed context. "
        "Do not claim user activity that is not returned by Mosaic."
    ),
)


def _request(path: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{API_BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


@mcp.tool()
def mosaic_search_memory(query: str, limit: int = 8, project_id: str | None = None, goal_id: str | None = None) -> dict[str, Any]:
    """Search local Mosaic memory and return evidence-backed results."""
    return _request("/context/ask", method="POST", body={
        "query": query,
        "limit": limit,
        "project_id": project_id,
        "goal_id": goal_id,
        "agent_name": "mcp",
    })


@mcp.tool()
def mosaic_get_current_context() -> dict[str, Any] | None:
    """Return the most recent reconstructed activity session."""
    return _request("/context/resume")


@mcp.tool()
def mosaic_get_projects() -> list[dict[str, Any]]:
    """List projects known to Mosaic."""
    return _request("/context/projects")


@mcp.tool()
def mosaic_get_goals() -> list[dict[str, Any]]:
    """List active and completed user goals known to Mosaic."""
    return _request("/context/goals")


@mcp.tool()
def mosaic_get_learning_graph() -> dict[str, Any]:
    """Return learning concepts, exposure signals and practice suggestions."""
    return _request("/context/learning")


@mcp.tool()
def mosaic_get_privacy_policy(agent_name: str = "mcp") -> dict[str, Any]:
    """Return the context firewall policy applied to this agent."""
    return _request(f"/context/policies/{urllib.parse.quote(agent_name, safe='')}")


@mcp.tool()
def mosaic_create_context_capsule(title: str, project_id: str | None = None, goal_id: str | None = None, limit: int = 12) -> dict[str, Any]:
    """Create a portable context capsule for resuming a task later."""
    return _request("/context/capsules", method="POST", body={
        "title": title,
        "project_id": project_id,
        "goal_id": goal_id,
        "limit": limit,
        "agent_name": "mcp",
    })


@mcp.resource("mosaic://current-context")
def current_context_resource() -> str:
    """Current Mosaic activity context as JSON."""
    return json.dumps(_request("/context/resume"), indent=2)


if __name__ == "__main__":
    mcp.run()
