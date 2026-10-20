#!/usr/bin/env python3
"""Live, read-only smoke test of the Chronicle MCP server over stdio.

Starts the server the way an MCP client would and exercises only read-only tools
against your real archive (CHRONICLE_BASE_DIR, or the configured default). Chats are
never modified; like any normal session, the server may create its default
mcp_config.json and refresh the derived .chronicle_index.json search cache. Exits
non-zero if any check fails.

Usage:
    python smoke_test_live.py                      # run ./chat_server.py with this Python
    python smoke_test_live.py --command chronicle-mcp-server
    python smoke_test_live.py --command docker run -i --rm -v "$HOME/.chronicle:/data" chronicle-mcp
"""

import argparse
import os
import shlex
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "search_history", "get_chat_logs", "sync_workspace_data", "compile_project_insights",
    "maintain_storage", "manage_session_state", "save_handoff_receipt", "get_handoff_status",
}
failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}{(': ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def text_of(result) -> str:
    return "\n".join(getattr(c, "text", "") for c in result.content)


async def main(command: list[str], query: str) -> None:
    # Pass the full environment: the SDK otherwise forwards only a small allow-list,
    # which would drop CHRONICLE_BASE_DIR / TRANSCRIPTS_DIR.
    params = StdioServerParameters(command=command[0], args=command[1:], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            check("initialize", init.serverInfo.name == "Chronicle MCP",
                  f"{init.serverInfo.name} {init.serverInfo.version}")
            check("instructions present", bool(init.instructions))

            tools = {t.name: t for t in (await session.list_tools()).tools}
            check("tools/list returns all 8 tools", set(tools) == EXPECTED_TOOLS, ", ".join(sorted(tools)))
            undocumented = [f"{t.name}.{p}" for t in tools.values()
                            for p, s in t.inputSchema.get("properties", {}).items() if not s.get("description")]
            check("every parameter documented", not undocumented, ", ".join(undocumented))
            check("every tool annotated", all(t.annotations for t in tools.values()))

            caps = await session.call_tool("maintain_storage", {"op_type": "capabilities"})
            check("maintain_storage capabilities", not caps.isError)

            listing = await session.call_tool("get_chat_logs", {"per_page": 20})
            files = [line.strip() for line in text_of(listing).splitlines() if line.strip().endswith(".json")]
            check("get_chat_logs list", not listing.isError, f"{len(files)} chats")

            for method in ("keyword", "semantic"):
                found = await session.call_tool("search_history", {"query": query, "method": method, "limit": 3})
                check(f"search_history {method}", not found.isError, text_of(found)[:100].replace("\n", " | "))

            if files:
                page = await session.call_tool(
                    "get_chat_logs", {"view_type": "content", "chat_id": files[0], "per_page": 2})
                check("get_chat_logs content", not page.isError, files[0])

            missing = await session.call_tool("get_chat_logs", {"chat_id": "__no_such_chat__.json"})
            check("missing chat reports isError", missing.isError)

            status = await session.call_tool("get_handoff_status", {})
            check("get_handoff_status", not status.isError, str(status.structuredContent)[:100])

            resources = {str(r.uri) for r in (await session.list_resources()).resources}
            check("resources listed", "chronicle://capabilities" in resources)
            prompts = {p.name for p in (await session.list_prompts()).prompts}
            check("prompts listed", {"start_session", "recall_past_work"} <= prompts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--query", default="mcp connector", help="Search query to try (default: %(default)s)")
    parser.add_argument("--command", nargs=argparse.REMAINDER,
                        help="Server command to launch (default: this Python running chat_server.py)")
    args = parser.parse_args()
    cmd = args.command or [sys.executable, str(Path(__file__).resolve().parent / "chat_server.py")]
    if len(cmd) == 1 and " " in cmd[0]:
        cmd = shlex.split(cmd[0])
    try:
        anyio.run(main, cmd, args.query)
    except Exception as exc:  # connection or protocol failure
        check("server session", False, repr(exc))
    print(f"\n{'OK' if not failures else 'FAILED'}: {len(failures)} failed check(s)")
    sys.exit(1 if failures else 0)
