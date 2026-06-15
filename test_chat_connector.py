"""Tests for Universal Chat Connector - all feature categories."""

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
        files = self.cc.get_chat_logs(client="default")
        self.assertIn("alpha.json", files)
        hits = self.cc.search_history(query="roblox", method="keyword")
        self.assertEqual(hits[0], "alpha__part_1.json")

    def test_read_range_and_save(self):
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(5)]
        result = self.cc.manage_session_state(action="save", conversation_name="test-save", messages=msgs, force_save=True)
        self.assertIn("Successfully saved", result)
        text = self.cc.get_chat_logs(chat_id="test-save.json", view_type="content", start_msg=1, end_msg=3)
        self.assertIn("msg 0", text)
        self.assertIn("of 5 total", text)

    def test_save_below_threshold(self):
        result = self.cc.manage_session_state(action="save", conversation_name="short", messages=[{"role": "user", "content": "hi"}])
        self.assertIn("below threshold", result)

    # ── High impact ─────────────────────────────────────────────────────────

    def test_metadata_merge_export_delete(self):
        self._write_chat("meta.json", [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ])
        meta = self.cc.get_chat_logs(chat_id="meta.json", view_type="metadata")
        self.assertEqual(meta["message_count"], 2)
        self.assertGreater(meta["file_size_bytes"], 0)

        merge_result = self.cc.manage_session_state(
            action="merge", file_name="meta.json", new_messages=[{"role": "user", "content": "follow up"}]
        )
        self.assertIn("total: 3", merge_result)

        export_result = self.cc.manage_session_state(action="export_markdown", file_name="meta.json")
        self.assertIn("Exported markdown", export_result)
        md_files = os.listdir(self.cc.exports_dir)
        self.assertTrue(any(f.endswith(".md") for f in md_files))

        blocked = self.cc.manage_session_state(action="delete", file_name="meta.json", confirm=False)
        self.assertIn("confirm=true", blocked)
        deleted = self.cc.manage_session_state(action="delete", file_name="meta.json", confirm=True)
        self.assertIn("Deleted", deleted)

    # ── Search and retrieval ─────────────────────────────────────────────────

    def test_semantic_summary_related_date_filter(self):
        self._write_chat("mcp_setup.json", [{"role": "user", "content": "configure mcp server stdio"}])
        self._write_chat("ui_page.json", [{"role": "user", "content": "design hero section navbar"}])
        semantic = self.cc.search_history(query="mcp server stdio connector", method="semantic", top_k=2)
        self.assertGreater(semantic[0]["score"], 0)
        self.assertEqual(semantic[0]["file"], "mcp_setup__part_1.json")

        summary = self.cc.get_chat_logs(chat_id="mcp_setup.json", view_type="summary")
        self.assertIn("configure mcp", summary)

        related = self.cc.search_history(query="mcp_setup.json", method="related", top_k=3)
        self.assertTrue(all("file" in r for r in related))

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filtered = self.cc.search_history(method="date_range", start_date=today, end_date=today)
        self.assertTrue(any(r.get("file_name") == "mcp_setup.json" for r in filtered))

    # ── Automation ──────────────────────────────────────────────────────────

    def test_auto_save_watch_import(self):
        msgs = [{"role": "user", "content": "session data"}]
        reg = self.cc.manage_session_state(action="register_auto_save", conversation_name="auto-session", messages=msgs)
        self.assertIn("registered", reg)
        saved = self.cc.manage_session_state(action="trigger_auto_save")
        self.assertIn("Successfully saved", saved)

        watch1 = self.cc.manage_session_state(action="watch_folder")
        self.assertIn("auto-session.json", watch1["new_files"])

        self._write_chat("watched.json", [{"role": "user", "content": "x"}])
        watch2 = self.cc.manage_session_state(action="watch_folder")
        self.assertIn("watched.json", watch2["new_files"])

        content = json.dumps({"messages": [{"role": "user", "content": "imported"}]})
        imported = self.cc.sync_workspace_data(source_type="raw_content", payload=content, title="pasted-chat")
        self.assertIn("Imported chat", imported)

        src = self._write_chat("source.json", [{"role": "user", "content": "from file"}])
        path_result = self.cc.sync_workspace_data(source_type="local_path", payload=src, title="from-local")
        self.assertIn("Imported chat", path_result)

    def test_sync_cursor_transcripts_missing_dir(self):
        cc = ChatConnector(base_dir=self.tmp, cursor_transcripts_dir="/nonexistent/path")
        result = cc.sync_workspace_data(source_type="cursor_agent_transcripts", limit=5)
        self.assertIn("error", result)

    # ── Intelligence ────────────────────────────────────────────────────────

    def test_action_items_index_compare_brief(self):
        self._write_chat("tasks.json", [
            {"role": "user", "content": "TODO: fix navbar\n- [ ] add dark mode"},
            {"role": "assistant", "content": "Action item: implement hero section"},
        ])
        items = self.cc.compile_project_insights(insight_type="action_items", file_name="tasks.json")
        self.assertTrue(any("navbar" in i.lower() or "dark mode" in i.lower() for i in items))

        self._write_chat("roblox.json", [{"role": "user", "content": "roblox avatar export"}])
        index = self.cc.compile_project_insights(insight_type="knowledge_index", rebuild=True)
        self.assertIn("roblox", index)
        self.assertIn("roblox.json", index["roblox"])

        compare = self.cc.compile_project_insights(insight_type="compare_chats", file_name_a="tasks.json", file_name_b="roblox.json")
        self.assertIn("Compare:", compare)

        brief = self.cc.compile_project_insights(
            insight_type="project_brief", target_chats=["tasks.json", "roblox.json"], brief_title="Test Brief"
        )
        self.assertIn("Brief written", brief)

    # ── Config and ops ──────────────────────────────────────────────────────

    def test_configure_compress_dedupe_capabilities(self):
        result = self.cc.maintain_storage(op_type="configure", settings={"auto_save_message_threshold": 5})
        self.assertIn("auto_save_message_threshold", result)
        self.assertEqual(self.cc.load_config()["auto_save_message_threshold"], 5)

        payload = {"title": "dup", "messages": [{"role": "user", "content": "same content"}]}
        for name in ("dup_a.json", "dup_b.json"):
            path = os.path.join(self.cc.resolve_chats_dir(), name)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        dry = self.cc.maintain_storage(op_type="deduplicate", dry_run=True)
        self.assertEqual(len(dry["duplicates"]), 1)

        caps = self.cc.maintain_storage(op_type="capabilities")
        self.assertEqual(caps["total_tools"], 6)
        self.assertIn("core", caps["tool_categories"])

    def test_client_paths(self):
        self.cc.maintain_storage(op_type="configure", settings={
            "client_paths": {"default": "chats", "testclient": "chats/testclient"}
        })
        self.cc.manage_session_state(
            action="save", conversation_name="client-chat", messages=[{"role": "user", "content": "x"}], force_save=True, client="testclient"
        )
        files = self.cc.get_chat_logs(client="testclient")
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
        res = self.cc.sync_workspace_data(source_type="agent_transcripts", client="continue", source_dir=trans_dir, limit=5)
        self.assertEqual(res["total_scanned"], 3)
        self.assertEqual(len(res["imported"]), 3)
        files = self.cc.get_chat_logs(client="continue")
        self.assertTrue(any("continue_t1" in f for f in files))
        self.assertTrue(any("continue_t2" in f for f in files))
        self.assertTrue(any("continue_t3" in f for f in files))
        shutil.rmtree(trans_dir, ignore_errors=True)

    def test_security_path_traversal(self):
        result = self.cc.get_chat_logs(chat_id="../secrets.json")
        self.assertIn("Security block", result)

    def test_temporal_decay(self):
        # Create identical chats with different mtimes
        alpha_path = self._write_chat("decay_alpha.json", [{"role": "user", "content": "unique keyword search testing"}])
        beta_path = self._write_chat("decay_beta.json", [{"role": "user", "content": "unique keyword search testing"}])
        
        import time
        now = time.time()
        past_45_days = now - (45 * 86400)
        past_1_day = now - (1 * 86400)
        
        os.utime(alpha_path, (past_45_days, past_45_days))
        os.utime(beta_path, (past_1_day, past_1_day))
        
        results = self.cc.search_chats_semantic(query="unique keyword search testing", top_k=2)
        self.assertEqual(len(results), 2)
        # The first result (highest score) must be decay_beta.json (newer)
        self.assertEqual(results[0]["file"], "decay_beta__part_1.json")
        self.assertEqual(results[1]["file"], "decay_alpha__part_1.json")
        self.assertGreater(results[0]["score"], results[1]["score"])

    def test_heuristic_summary_pruning(self):
        messages = [
            {"role": "user", "content": "initial issue description"},
            {"role": "assistant", "content": "intermediate message with no keywords"},
            {"role": "user", "content": "another intermediate message containing keyword error"},
            {"role": "assistant", "content": "intermediate message containing code block\n```python\nprint('hello')\n```"},
            {"role": "assistant", "content": "final assistant reply"}
        ]
        chat_path = self._write_chat("pruned_chat.json", messages)
        
        import time
        now = time.time()
        past_20_days = now - (20 * 86400)
        os.utime(chat_path, (past_20_days, past_20_days))
        
        # summary_pruning_days_threshold defaults to 14, so 20 days is older and should trigger pruning
        result = self.cc.read_chat_message_range("pruned_chat.json", summarize_code=False)
        self.assertIn("Pruned Historical Transcript", result)
        self.assertIn("initial issue description", result)
        self.assertIn("another intermediate message containing keyword error", result)
        self.assertIn("print('hello')", result)
        self.assertIn("final assistant reply", result)
        # The message without keywords or code blocks should be pruned
        self.assertNotIn("intermediate message with no keywords", result)

    def test_serialized_state_indexing(self):
        # Create a new chat and sync using the save action to trigger index creation
        self.cc.manage_session_state(
            action="save",
            conversation_name="index_alpha",
            messages=[{"role": "user", "content": "indexing verification test"}],
            force_save=True
        )
        
        # Verify index was written and contains keywords
        index_file = self.cc.serialized_index_path
        self.assertTrue(os.path.exists(index_file))
        
        with open(index_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("timestamps", data)
        self.assertIn("index", data)
        
        # Verify searching by keyword uses the index and finds it
        hits = self.cc.search_history(query="verification", method="keyword")
        self.assertIn("index_alpha__part_1.json", hits)
        
        # Delete the file and check that the index is updated
        self.cc.manage_session_state(action="delete", file_name="index_alpha__part_1.json", confirm=True)
        hits2 = self.cc.search_history(query="verification", method="keyword")
        self.assertNotIn("index_alpha__part_1.json", hits2)

    def test_okapi_bm25_relevance_ranking(self):
        # Doc 1: Very short document
        self._write_chat("short_doc.json", [
            {"role": "user", "content": "specialquery"}
        ])
        # Doc 2: Very long document repeating other words but containing 'specialquery' once
        long_content = "otherword " * 100 + "specialquery" + " otherword" * 100
        self._write_chat("long_doc.json", [
            {"role": "user", "content": long_content}
        ])
        
        # Sync index
        self.cc._sync_serialized_index("default")
        
        # Search semantically using our BM25 scorer
        results = self.cc.search_chats_semantic(query="specialquery", top_k=2)
        self.assertEqual(len(results), 2)
        
        # The first result (highest score) must be the short document part
        self.assertIn("short_doc", results[0]["file"])
        self.assertIn("long_doc", results[1]["file"])
        self.assertGreater(results[0]["score"], results[1]["score"])

        # Check keyword search too
        hits = self.cc.search_history(query="specialquery", method="keyword")
        self.assertEqual(len(hits), 2)
        self.assertIn("short_doc", hits[0])
        self.assertIn("long_doc", hits[1])

    def test_temporal_session_splitting(self):
        import time
        now = time.time()
        # Create a conversation with 3 messages:
        # Msg 1 at t
        # Msg 2 at t + 600 (10 mins later)
        # Msg 3 at t + 3000 (50 mins later -> gap of 40 mins, triggers temporal split)
        messages = [
            {"role": "user", "content": "message one", "timestamp": now},
            {"role": "assistant", "content": "message two", "timestamp": now + 600},
            {"role": "user", "content": "message three", "timestamp": now + 3000}
        ]
        self._write_chat("temporal_split.json", messages)
        
        # Trigger index update
        self.cc._update_file_index("temporal_split.json", "default")
        
        # Look at the serialized index to see the logical parts
        index_data = self.cc._load_serialized_index()
        doc_lengths = index_data.get("doc_lengths", {})
        
        # We expect two logical parts for temporal_split.json:
        # temporal_split__part_1.json (containing message one and two)
        # temporal_split__part_2.json (containing message three)
        part_1_key = "default/temporal_split__part_1.json"
        part_2_key = "default/temporal_split__part_2.json"
        
        self.assertIn(part_1_key, doc_lengths)
        self.assertIn(part_2_key, doc_lengths)
        
        # Check range reading of individual parts
        part_1_text = self.cc.read_chat_message_range("temporal_split__part_1.json")
        self.assertIn("message one", part_1_text)
        self.assertIn("message two", part_1_text)
        self.assertNotIn("message three", part_1_text)
        
        part_2_text = self.cc.read_chat_message_range("temporal_split__part_2.json")
        self.assertNotIn("message one", part_2_text)
        self.assertNotIn("message two", part_2_text)
        self.assertIn("message three", part_2_text)

    def test_turn_based_session_splitting(self):
        # 35 messages, no timestamp gaps
        messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"turnmsg_{i}"} for i in range(35)]
        self._write_chat("turn_split.json", messages)
        
        # Trigger index update
        self.cc._update_file_index("turn_split.json", "default")
        
        index_data = self.cc._load_serialized_index()
        doc_lengths = index_data.get("doc_lengths", {})
        
        part_1_key = "default/turn_split__part_1.json"
        part_2_key = "default/turn_split__part_2.json"
        part_3_key = "default/turn_split__part_3.json"
        
        self.assertIn(part_1_key, doc_lengths)
        self.assertIn(part_2_key, doc_lengths)
        self.assertNotIn(part_3_key, doc_lengths) # Only 2 parts expected (0-19 and 16-34)
        
        # Verify message contents for part 1 and part 2 (checking the 4-message overlap: 16, 17, 18, 19)
        part_1_text = self.cc.read_chat_message_range("turn_split__part_1.json", start_msg=1, end_msg=30)
        self.assertIn("turnmsg_0", part_1_text)
        self.assertIn("turnmsg_19", part_1_text)
        self.assertNotIn("turnmsg_20", part_1_text)
        
        part_2_text = self.cc.read_chat_message_range("turn_split__part_2.json", start_msg=1, end_msg=30)
        self.assertNotIn("turnmsg_15", part_2_text)
        self.assertIn("turnmsg_16", part_2_text)
        self.assertIn("turnmsg_34", part_2_text)

    def test_logical_part_file_operations(self):
        messages = [{"role": "user", "content": "hello there action item: fix code"}]
        self._write_chat("ops_file.json", messages)
        self.cc._update_file_index("ops_file.json", "default")
        
        # Resolve metadata on part 1
        meta = self.cc.get_chat_logs(chat_id="ops_file__part_1.json", view_type="metadata")
        self.assertEqual(meta["message_count"], 1)
        self.assertEqual(meta["file_name"], "ops_file.json")
        
        # Resolve summary on part 1
        summary = self.cc.get_chat_logs(chat_id="ops_file__part_1.json", view_type="summary")
        self.assertIn("hello there", summary)
        
        # Resolve action items on part 1 using compile_project_insights
        items = self.cc.compile_project_insights(insight_type="action_items", file_name="ops_file__part_1.json")
        self.assertTrue(any("fix code" in i for i in items))
        
        # Delete using part 1
        del_result = self.cc.manage_session_state(action="delete", file_name="ops_file__part_1.json", confirm=True)
        self.assertIn("Deleted", del_result)
        
        # Verify physical file is gone
        path = os.path.join(self.cc.resolve_chats_dir("default"), "ops_file.json")
        self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
