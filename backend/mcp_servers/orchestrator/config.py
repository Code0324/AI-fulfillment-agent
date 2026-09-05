"""Orchestrator server configuration.

Loads the list of child MCP servers (name + how to launch it over stdio)
from a JSON file — mcp_servers.json by default, next to this module —
so servers can be added or removed without touching client_manager.py.
Override the path with the MCP_ORCHESTRATOR_CONFIG environment variable.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# backend/ — the directory every child server's "python -m mcp_servers.X.server"
# must run from so `app` and `mcp_servers` are both importable, regardless of
# the orchestrator process's own working directory.
BACKEND_DIR = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "mcp_servers.json"


@dataclass
class ServerConfig:
    """Launch info for one child MCP server, connected over stdio."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    cwd: str = str(BACKEND_DIR)
    env: dict[str, str] | None = None


def load_server_configs(path: str | Path | None = None) -> list[ServerConfig]:
    """Load and validate the child-server list from JSON.

    Raises FileNotFoundError / ValueError with a clear message rather than
    silently returning an empty list — a misconfigured orchestrator should
    fail loudly at startup, not connect to nothing.
    """
    config_path = Path(path or os.getenv("MCP_ORCHESTRATOR_CONFIG") or DEFAULT_CONFIG_PATH)
    if not config_path.is_file():
        raise FileNotFoundError(f"MCP orchestrator config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    servers_raw = raw.get("servers")
    if not isinstance(servers_raw, list) or not servers_raw:
        raise ValueError(f"{config_path} must define a non-empty 'servers' list")

    configs: list[ServerConfig] = []
    seen_names: set[str] = set()
    for entry in servers_raw:
        name = entry.get("name")
        command = entry.get("command")
        if not name or not command:
            raise ValueError(f"Each server entry needs 'name' and 'command': {entry}")
        if name in seen_names:
            raise ValueError(f"Duplicate server name in {config_path}: {name}")
        seen_names.add(name)
        configs.append(
            ServerConfig(
                name=name,
                command=command,
                args=list(entry.get("args", [])),
                cwd=str(entry.get("cwd") or BACKEND_DIR),
                env=entry.get("env"),
            )
        )
    return configs
