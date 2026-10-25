"""Consistency checks for the MCPB bundle in this folder (run by CI).

Checks that mcpb/manifest.json, mcpb/server/main.py, pyproject.toml and
server.json all name the same version, that the manifest uses a server type the
Smithery CLI can publish, and that the manifest's tool list matches the tools
the server actually registers. Run from the repository root after
``pip install .``:

    python mcpb/check_bundle.py
"""

import asyncio
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "mcpb"


def main() -> int:
    errors = []
    manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    launcher = (BUNDLE / "server" / "main.py").read_text(encoding="utf-8")

    version = pyproject["project"]["version"]
    package = pyproject["project"]["name"]
    launcher_version = re.search(r'^VERSION = "([^"]+)"', launcher, re.M)
    found = {
        "mcpb/manifest.json version": manifest.get("version"),
        "mcpb/server/main.py VERSION": launcher_version and launcher_version.group(1),
        "server.json version": registry.get("version"),
    }
    for where, value in found.items():
        if value != version:
            errors.append(f"{where} is {value!r}, pyproject.toml is {version!r}")

    server = manifest.get("server", {})
    # `smithery mcp publish` infers the bundle runtime from server.type and only
    # recognizes node, python and binary (not the MCPB 0.4 "uv" type).
    if server.get("type") not in {"python", "node", "binary"}:
        errors.append(f"server.type {server.get('type')!r} cannot be published with the Smithery CLI")
    args = server.get("mcp_config", {}).get("args", [])
    if f"{package}=={version}" not in args:
        errors.append(f"mcp_config.args {args!r} does not pin {package}=={version}")
    entry = BUNDLE / server.get("entry_point", "")
    if not entry.is_file():
        errors.append(f"entry_point {server.get('entry_point')!r} does not exist")
    if not (BUNDLE / manifest.get("icon", "")).is_file():
        errors.append(f"icon {manifest.get('icon')!r} does not exist")

    sys.path.insert(0, str(ROOT))
    import chat_server

    live = {tool.name for tool in asyncio.run(chat_server.mcp.list_tools())}
    declared = {tool["name"] for tool in manifest.get("tools", [])}
    if live != declared:
        errors.append(
            f"manifest tools differ from the server: missing {sorted(live - declared)}, "
            f"extra {sorted(declared - live)}"
        )

    for error in errors:
        print(f"::error::{error}")
    if not errors:
        print(f"MCPB manifest OK: {manifest['name']} {version}, {len(declared)} tools")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
