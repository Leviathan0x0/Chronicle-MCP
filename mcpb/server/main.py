"""Launcher for the Chronicle MCP bundle (MCPB).

The manifest's ``mcp_config`` runs ``uvx chronicle-mcp-server==<version>``
directly, so hosts normally never execute this file. It is the bundle's
declared ``entry_point`` and a fallback: run it with Python and it starts the
same pinned release from PyPI with uvx, or an already installed
``chronicle-mcp-server`` console script when uv is not available.
"""

import os
import shutil
import sys

PACKAGE = "chronicle-mcp-server"
VERSION = "1.6.2"  # Kept equal to manifest.json and pyproject.toml by CI.


def main() -> None:
    uvx = shutil.which("uvx")
    if uvx:
        os.execv(uvx, [uvx, f"{PACKAGE}=={VERSION}", *sys.argv[1:]])
    installed = shutil.which(PACKAGE)
    if installed:
        os.execv(installed, [installed, *sys.argv[1:]])
    sys.stderr.write(
        f"Chronicle MCP needs uv (https://docs.astral.sh/uv/) or `pip install {PACKAGE}=={VERSION}`.\n"
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
