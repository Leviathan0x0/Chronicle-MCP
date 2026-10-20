"""Introspect the real server over stdio, the way MCP clients see it.

These tests guard tool-definition quality (descriptions, parameter docs, enums,
annotations, titles), server metadata, error reporting, and version consistency.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import chat_core

ROOT = Path(__file__).resolve().parent
EXPECTED_TOOLS = {
    "search_history",
    "get_chat_logs",
    "sync_workspace_data",
    "compile_project_insights",
    "maintain_storage",
    "manage_session_state",
    "save_handoff_receipt",
    "get_handoff_status",
}
HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")
DISCRIMINATORS = {
    "search_history": "method",
    "get_chat_logs": "view_type",
    "sync_workspace_data": "source_type",
    "compile_project_insights": "insight_type",
    "maintain_storage": "op_type",
    "manage_session_state": "action",
}


def _property_has_enum(schema: dict) -> bool:
    if schema.get("enum"):
        return True
    return any(_property_has_enum(s) for s in schema.get("anyOf", []))


class ServerIntrospectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_dir = tempfile.mkdtemp(prefix="chronicle_introspect_")
        cls.work_dir = tempfile.mkdtemp(prefix="chronicle_cwd_")
        env = dict(os.environ)
        env["CHRONICLE_BASE_DIR"] = cls.base_dir
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        params = StdioServerParameters(
            command=sys.executable, args=[str(ROOT / "chat_server.py")], env=env, cwd=cls.work_dir
        )

        async def collect():
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    tools = (await session.list_tools()).tools
                    prompts = (await session.list_prompts()).prompts
                    resources = (await session.list_resources()).resources
                    calls = {
                        "missing_file": await session.call_tool("get_chat_logs", {"chat_id": "missing.json"}),
                        "bad_enum": await session.call_tool("maintain_storage", {"op_type": "bogus"}),
                        "bad_bound": await session.call_tool("search_history", {"query": "x", "top_k": 0}),
                        "empty_list": await session.call_tool("get_chat_logs", {}),
                        "capabilities": await session.call_tool("maintain_storage", {"op_type": "capabilities"}),
                        "handoff": await session.call_tool("get_handoff_status", {}),
                    }
                    resource = await session.read_resource("chronicle://capabilities")
                    prompt = await session.get_prompt("recall_past_work", {"topic": "auth bug"})
                    return init, tools, prompts, resources, calls, resource, prompt

        (cls.init, cls.tools, cls.prompts, cls.resources, cls.calls, cls.resource, cls.prompt) = anyio.run(collect)
        cls.by_name = {t.name: t for t in cls.tools}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base_dir, ignore_errors=True)
        shutil.rmtree(cls.work_dir, ignore_errors=True)

    # ── Server metadata ─────────────────────────────────────────────────────

    def test_server_info(self):
        self.assertEqual(self.init.serverInfo.name, "Chronicle MCP")
        self.assertEqual(self.init.serverInfo.version, chat_core.__version__)
        self.assertTrue(self.init.instructions and len(self.init.instructions) > 200)
        for name in EXPECTED_TOOLS:
            self.assertIn(name, self.init.instructions, f"instructions should route to {name}")

    def test_startup_does_not_write_into_working_directory(self):
        self.assertEqual(os.listdir(self.work_dir), [])

    # ── Tool definitions ────────────────────────────────────────────────────

    def test_exact_tool_set(self):
        self.assertEqual(set(self.by_name), EXPECTED_TOOLS)

    def test_every_tool_has_title_and_substantial_description(self):
        for tool in self.tools:
            with self.subTest(tool=tool.name):
                self.assertTrue(tool.title, "missing title")
                self.assertGreaterEqual(len(tool.description or ""), 300, "description too thin")
                lowered = tool.description.lower()
                self.assertTrue(
                    re.search(r"\buse (it|this)\b|\bcall it\b", lowered), "description should say when to use it"
                )
                self.assertTrue("return" in lowered, "description should say what it returns")

    def test_every_tool_has_all_annotations(self):
        for tool in self.tools:
            with self.subTest(tool=tool.name):
                self.assertIsNotNone(tool.annotations, "missing annotations")
                for hint in HINTS:
                    self.assertIsNotNone(getattr(tool.annotations, hint), f"{hint} not set")
                self.assertFalse(tool.annotations.openWorldHint, "Chronicle is local-only")
                if tool.annotations.readOnlyHint:
                    self.assertFalse(tool.annotations.destructiveHint)

    def test_destructive_tools_are_flagged(self):
        self.assertTrue(self.by_name["manage_session_state"].annotations.destructiveHint)
        self.assertTrue(self.by_name["maintain_storage"].annotations.destructiveHint)
        for name in ("search_history", "get_chat_logs", "get_handoff_status"):
            self.assertTrue(self.by_name[name].annotations.readOnlyHint, name)

    def test_every_parameter_has_a_description(self):
        for tool in self.tools:
            props = tool.inputSchema.get("properties", {})
            for param, schema in props.items():
                with self.subTest(tool=tool.name, param=param):
                    self.assertTrue((schema.get("description") or "").strip(), "missing description")

    def test_operation_selectors_are_enums(self):
        for tool, param in DISCRIMINATORS.items():
            with self.subTest(tool=tool, param=param):
                schema = self.by_name[tool].inputSchema["properties"][param]
                self.assertTrue(_property_has_enum(schema), "selector must be an enum")

    def test_counts_have_lower_bounds(self):
        for tool, param in [("search_history", "limit"), ("search_history", "top_k"),
                            ("get_chat_logs", "page"), ("get_chat_logs", "per_page"),
                            ("get_chat_logs", "start_msg"), ("get_chat_logs", "max_msg_len")]:
            with self.subTest(tool=tool, param=param):
                self.assertIn("minimum", self.by_name[tool].inputSchema["properties"][param])

    # ── Prompts and resources ───────────────────────────────────────────────

    def test_prompts_documented(self):
        names = {p.name for p in self.prompts}
        self.assertTrue({"start_session", "recall_past_work"} <= names)
        for prompt in self.prompts:
            with self.subTest(prompt=prompt.name):
                self.assertTrue(prompt.title and prompt.description)
                for arg in prompt.arguments or []:
                    self.assertTrue(arg.description, f"argument {arg.name} undocumented")
        self.assertIn("auth bug", self.prompt.messages[0].content.text)

    def test_resources_documented_and_readable(self):
        uris = {str(r.uri) for r in self.resources}
        self.assertTrue({"chronicle://capabilities", "chronicle://chats"} <= uris)
        for resource in self.resources:
            self.assertTrue(resource.description and resource.mimeType)
        caps = json.loads(self.resource.contents[0].text)
        self.assertEqual(caps["version"], chat_core.__version__)

    # ── Results and errors ──────────────────────────────────────────────────

    def test_execution_errors_set_is_error(self):
        for key in ("missing_file", "bad_enum", "bad_bound"):
            with self.subTest(call=key):
                self.assertTrue(self.calls[key].isError)
        self.assertIn("missing.json", self.calls["missing_file"].content[0].text)

    def test_normal_results_are_not_errors(self):
        for key in ("empty_list", "capabilities", "handoff"):
            with self.subTest(call=key):
                self.assertFalse(self.calls[key].isError)
        caps = self.calls["capabilities"].structuredContent["result"]
        self.assertEqual(caps["total_tools"], len(EXPECTED_TOOLS))
        self.assertEqual(self.calls["handoff"].structuredContent["blocked"], False)


class VersionConsistencyTests(unittest.TestCase):
    def test_versions_match(self):
        version = chat_core.__version__
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(f'version = "{version}"', pyproject)
        server = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
        self.assertEqual(server["version"], version)
        for package in server["packages"]:
            self.assertEqual(package["version"], version)
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        first_entry = re.search(r"^## \[?(\d+\.\d+\.\d+)", changelog, re.M)
        self.assertEqual(first_entry.group(1), version)

    def test_server_json_description_fits_registry_limit(self):
        server = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
        self.assertLessEqual(len(server["description"]), 100)

    def test_mcp_dependency_is_capped_below_2(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertRegex(pyproject, r'"mcp>=1\.\d+,<2"')


if __name__ == "__main__":
    unittest.main()
