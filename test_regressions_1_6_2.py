"""Regression tests for bugs found in the 1.6.2 audit."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from chat_core import ChatConnector, _contains_keyword

ROOT = Path(__file__).resolve().parent


def _receipt(cc: ChatConnector, **kwargs) -> str:
    return cc.save_handoff_receipt(
        obligations={"promise": "p", "scope": []},
        work_state={"touched_surfaces": []},
        evidence={"checks_run": []},
        invalidation={"stale_if": [], "next_safe_action": "next"},
        **kwargs,
    )


class HandoffCollisionTests(unittest.TestCase):
    def test_same_second_receipts_do_not_overwrite(self):
        cc = ChatConnector(base_dir=tempfile.mkdtemp())
        with mock.patch("time.time", return_value=1_800_000_000.25):
            first = _receipt(cc)
            second = _receipt(cc)
        self.assertNotEqual(first, second)
        files = [f for f in os.listdir(cc.chats_dir) if f.startswith("handoff_")]
        self.assertEqual(len(files), 2)
        ids = {json.load(open(os.path.join(cc.chats_dir, f)))["receipt_id"] for f in files}
        self.assertEqual(len(ids), 2)
        state = cc.get_workspace_handoff_state()
        self.assertIn(state["newest_receipt_id"], ids)

    def test_result_reports_receipt_id(self):
        cc = ChatConnector(base_dir=tempfile.mkdtemp())
        result = _receipt(cc, receipt_id="explicit-1")
        self.assertIn("(receipt_id: explicit-1)", result)


class TopicTaggingTests(unittest.TestCase):
    def test_keywords_match_whole_words(self):
        self.assertFalse(_contains_keyword("how do i build this", "ui"))
        self.assertTrue(_contains_keyword("fix the ui layout", "ui"))
        self.assertFalse(_contains_keyword("rapid prototyping", "api"))
        self.assertTrue(_contains_keyword("call the api.", "api"))
        self.assertTrue(_contains_keyword("a landing page draft", "landing page"))

    def test_build_is_not_ui_design(self):
        cc = ChatConnector(base_dir=tempfile.mkdtemp())
        with open(os.path.join(cc.chats_dir, "mcp.json"), "w", encoding="utf-8") as f:
            json.dump({"title": "t", "messages": [{"role": "user", "content": "build an mcp connector"}]}, f)
        index = cc.build_knowledge_index(rebuild=True)
        self.assertIn("mcp.json", index["mcp"])
        self.assertNotIn("mcp.json", index["ui_design"])


class CliTests(unittest.TestCase):
    def _run(self, code: str, env_extra: dict) -> str:
        home = tempfile.mkdtemp()
        env = {k: v for k, v in os.environ.items() if k != "CHRONICLE_BASE_DIR"}
        env.update({"HOME": home, "USERPROFILE": home, "PYTHONPATH": str(ROOT)})
        settings = Path(home) / ".chronicle_settings.json"
        settings.write_text(json.dumps({"chats_folder": "/from/settings"}), encoding="utf-8")
        env.update(env_extra)
        out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.strip()

    def test_explicit_base_dir_env_wins_over_saved_settings(self):
        code = "import os, cli; print(os.environ['CHRONICLE_BASE_DIR'])"
        self.assertEqual(self._run(code, {"CHRONICLE_BASE_DIR": "/from/env"}), "/from/env")

    def test_saved_settings_still_apply_without_env(self):
        import cli

        code = "import os, cli; print(os.environ.get('CHRONICLE_BASE_DIR', ''))"
        if cli.CHATS_FOLDER_KEY != "chats_folder":
            self.skipTest("settings key changed")
        self.assertEqual(self._run(code, {}), "/from/settings")

    def test_version_flag(self):
        out = subprocess.run(
            [sys.executable, "-c", "import sys, cli; sys.argv=['chronicle','--version']; cli.main()"],
            capture_output=True, text=True, timeout=60, cwd=str(ROOT),
        )
        self.assertIn("chronicle-mcp-server", out.stdout)


if __name__ == "__main__":
    unittest.main()
