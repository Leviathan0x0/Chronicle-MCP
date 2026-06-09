"""Tests for Universal Chat Connector — all feature categories."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from chat_core import ChatConnector, parse_to_plain_text


class ChatConnectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cc = ChatConnector(base_dir=self.tmp)

    def _write_chat(self, name: str, messages: list[dict], client: str = "default") -> str:
        path = os.path.join(self.cc.resolve_chats_dir(client), name)
        payload = {"title": name.replace(".json", ""), "messages": messages}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        return path

    # ── Core ────────────────────────────────────────────────────────────────

    def test_list_and_search(self):
        self._write_chat("alpha.json", [{"role": "user", "content": "roblox game dev"}])
        self._write_chat("beta.json", [{"role": "user", "content": "landing page ui"}])
        files = self.cc.list_all_stored_chats()
        self.assertIn("alpha.json", files)
        hits = self.cc.search_chats_by_keywords(["roblox"])
        self.assertEqual(hits[0], "alpha.json")

    def test_read_range_and_save(self):
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(5)]
        result = self.cc.save_current_conversation_state("test-save", msgs, force_save=True)
        self.assertIn("Successfully saved", result)
        text = self.cc.read_chat_message_range("test-save.json", 1, 3)
        self.assertIn("msg 0", text)
        self.assertIn("of 5 total", text)

    def test_save_below_threshold(self):
        result = self.cc.save_current_conversation_state("short", [{"role": "user", "content": "hi"}])
        self.assertIn("below threshold", result)

    # ── High impact ─────────────────────────────────────────────────────────

    def test_metadata_merge_export_delete(self):
        self._write_chat("meta.json", [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ])
        meta = self.cc.get_chat_metadata("meta.json")
        self.assertEqual(meta["message_count"], 2)
        self.assertGreater(meta["file_size_bytes"], 0)

        merge_result = self.cc.merge_conversation_into_archive(
            "meta.json", [{"role": "user", "content": "follow up"}]
        )
        self.assertIn("total: 3", merge_result)

        export_result = self.cc.export_chat_as_markdown("meta.json")
        self.assertIn("Exported markdown", export_result)
        md_files = os.listdir(self.cc.exports_dir)
        self.assertTrue(any(f.endswith(".md") for f in md_files))

        blocked = self.cc.delete_stored_chat("meta.json", confirm=False)
        self.assertIn("confirm=true", blocked)
        deleted = self.cc.delete_stored_chat("meta.json", confirm=True)
        self.assertIn("Deleted", deleted)

    # ── Search and retrieval ─────────────────────────────────────────────────

    def test_semantic_summary_related_date_filter(self):
        self._write_chat("mcp_setup.json", [{"role": "user", "content": "configure mcp server stdio"}])
        self._write_chat("ui_page.json", [{"role": "user", "content": "design hero section navbar"}])
        semantic = self.cc.search_chats_semantic("mcp server stdio connector", top_k=2)
        self.assertGreater(semantic[0]["score"], 0)
        self.assertEqual(semantic[0]["file"], "mcp_setup.json")

        summary = self.cc.get_chat_summary("mcp_setup.json")
        self.assertIn("configure mcp", summary)

        related = self.cc.find_related_chats("mcp_setup.json", top_k=3)
        self.assertTrue(all("file" in r for r in related))

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filtered = self.cc.filter_chats_by_date_range(today, today)
        self.assertTrue(any(r.get("file_name") == "mcp_setup.json" for r in filtered))

    # ── Automation ──────────────────────────────────────────────────────────

    def test_auto_save_watch_import(self):
        msgs = [{"role": "user", "content": "session data"}]
        reg = self.cc.register_session_for_auto_save("auto-session", msgs)
        self.assertIn("registered", reg)
        saved = self.cc.trigger_auto_save_on_session_end()
        self.assertIn("Successfully saved", saved)

        watch1 = self.cc.watch_chats_folder()
        self.assertIn("auto-session.json", watch1["new_files"])

        self._write_chat("watched.json", [{"role": "user", "content": "x"}])
        watch2 = self.cc.watch_chats_folder()
        self.assertIn("watched.json", watch2["new_files"])

        content = json.dumps({"messages": [{"role": "user", "content": "imported"}]})
        imported = self.cc.import_chat_from_content("pasted-chat", content)
        self.assertIn("Imported chat", imported)

        src = self._write_chat("source.json", [{"role": "user", "content": "from file"}])
        path_result = self.cc.import_chat_from_local_path(src, title="from-local")
        self.assertIn("Imported chat", path_result)

    def test_sync_cursor_transcripts_missing_dir(self):
        cc = ChatConnector(base_dir=self.tmp, cursor_transcripts_dir="/nonexistent/path")
        result = cc.sync_cursor_agent_transcripts(limit=5)
        self.assertIn("error", result)

    # ── Intelligence ────────────────────────────────────────────────────────

    def test_action_items_index_compare_brief(self):
        self._write_chat("tasks.json", [
            {"role": "user", "content": "TODO: fix navbar\n- [ ] add dark mode"},
            {"role": "assistant", "content": "Action item: implement hero section"},
        ])
        items = self.cc.extract_action_items("tasks.json")
        self.assertTrue(any("navbar" in i.lower() or "dark mode" in i.lower() for i in items))

        self._write_chat("roblox.json", [{"role": "user", "content": "roblox avatar export"}])
        index = self.cc.build_knowledge_index(rebuild=True)
        self.assertIn("roblox", index)
        self.assertIn("roblox.json", index["roblox"])

        compare = self.cc.compare_two_chats("tasks.json", "roblox.json")
        self.assertIn("Compare:", compare)

        brief = self.cc.generate_project_brief_from_chats(
            ["tasks.json", "roblox.json"], brief_title="Test Brief"
        )
        self.assertIn("Brief written", brief)

    # ── Config and ops ──────────────────────────────────────────────────────

    def test_configure_compress_dedupe_capabilities(self):
        result = self.cc.configure_connector_settings({"auto_save_message_threshold": 5})
        self.assertIn("auto_save_message_threshold", result)
        self.assertEqual(self.cc.load_config()["auto_save_message_threshold"], 5)

        payload = {"title": "dup", "messages": [{"role": "user", "content": "same content"}]}
        for name in ("dup_a.json", "dup_b.json"):
            path = os.path.join(self.cc.resolve_chats_dir(), name)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        dry = self.cc.deduplicate_stored_chats(dry_run=True)
        self.assertEqual(len(dry["duplicates"]), 1)

        caps = self.cc.get_server_capabilities()
        self.assertEqual(caps["total_tools"], 25)
        self.assertIn("intelligence", caps["tool_categories"])

    def test_client_paths(self):
        self.cc.configure_connector_settings({
            "client_paths": {"default": "chats", "testclient": "chats/testclient"}
        })
        self.cc.save_current_conversation_state(
            "client-chat", [{"role": "user", "content": "x"}], force_save=True, client="testclient"
        )
        files = self.cc.list_all_stored_chats(client="testclient")
        self.assertIn("client-chat.json", files)

    def test_parse_claude_chat_messages_format(self):
        data = {
            "chat_messages": [
                {"sender": "human", "text": "hello claude"},
                {"sender": "assistant", "text": "hi back"},
            ]
        }
        plain = parse_to_plain_text(data)
        self.assertEqual(len(plain), 2)
        self.assertTrue(plain[0].startswith("U:"))

    def test_parse_chatgpt_mapping_format(self):
        data = {
            "mapping": {
                "a": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["hello gpt"]},
                        "create_time": 2,
                    }
                },
                "b": {
                    "message": {
                        "author": {"role": "assistant"},
                        "content": {"parts": ["hi there"]},
                        "create_time": 3,
                    }
                },
            }
        }
        plain = parse_to_plain_text(data)
        self.assertEqual(len(plain), 2)
        self.assertTrue(plain[0].startswith("U:"))

    def test_sync_agent_transcripts_universal(self):
        import shutil
        trans_dir = tempfile.mkdtemp()
        with open(os.path.join(trans_dir, "t1.json"), "w", encoding="utf-8") as f:
            json.dump({"messages": [{"role": "user", "content": "hello from json"}]}, f)
        with open(os.path.join(trans_dir, "t2.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"role": "assistant", "content": "hello from jsonl"}) + "\n")
        with open(os.path.join(trans_dir, "t3.md"), "w", encoding="utf-8") as f:
            f.write("## User\nhello from md\n")
        res = self.cc.sync_agent_transcripts("continue", source_dir=trans_dir, limit=5)
        self.assertEqual(res["total_scanned"], 3)
        self.assertEqual(len(res["imported"]), 3)
        files = self.cc.list_all_stored_chats(client="continue")
        self.assertTrue(any("continue_t1" in f for f in files))
        self.assertTrue(any("continue_t2" in f for f in files))
        self.assertTrue(any("continue_t3" in f for f in files))
        shutil.rmtree(trans_dir, ignore_errors=True)

    def test_security_path_traversal(self):
        result = self.cc.read_chat_message_range("../secrets.json")
        self.assertIn("Security block", result)


if __name__ == "__main__":
    unittest.main()
