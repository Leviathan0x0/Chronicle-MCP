"""Tests for Universal Chat Connector - all feature categories."""

import concurrent.futures
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone

import cli
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
        self.assertEqual(caps["total_tools"], 8)
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

    def test_cli_setup_wizard_mocked_run(self):
        import sys
        import subprocess
        # Inputs:
        # Phase 1: Enter (skip split) -> ""
        # Phase 2: Enter (default storage path) -> ""
        # Phase 3: "1, 2" (select Cursor and VS Code) -> "1, 2"
        inputs = "\n\n1, 2\n"
        
        env = dict(os.environ)
        env["HOME"] = self.tmp
        
        process = subprocess.Popen(
            [sys.executable, "cli.py", "setup"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        stdout, stderr = process.communicate(input=inputs, timeout=5)
        
        self.assertEqual(process.returncode, 0)
        self.assertIn("Chronicle Archive Setup", stdout)
        self.assertIn("Chronicle Environment Live", stdout)
        self.assertIn("Storage Folder", stdout)
        self.assertIn("Cursor", stdout)
        self.assertIn("VS Code", stdout)

    def test_cli_setup_wizard_invalid_fallback(self):
        import sys
        import subprocess
        # Inputs:
        # Phase 1: Enter (skip split) -> ""
        # Phase 2: Enter (default storage path) -> ""
        # Phase 3: "1, 10" (select Cursor and Other) -> "1, 10"
        # Enter name of custom app -> "MyInvalidIDE"
        # Proceed with installing to valid cursor -> "y"
        inputs = "\n\n1, 10\nMyInvalidIDE\ny\n"
        
        env = dict(os.environ)
        env["HOME"] = self.tmp
        
        process = subprocess.Popen(
            [sys.executable, "cli.py", "setup"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        stdout, stderr = process.communicate(input=inputs, timeout=5)
        
        self.assertEqual(process.returncode, 0)
        self.assertIn('App/IDE "myinvalidide" was not found on your system.', stdout)
        self.assertIn("Would you like to proceed with installing", stdout)
        self.assertIn("Cursor", stdout)

    def test_cli_setup_wizard_antigravity_fallback(self):
        import sys
        import subprocess
        # Inputs:
        # Phase 1: Enter (skip split) -> ""
        # Phase 2: Enter (default storage path) -> ""
        # Phase 3: "8" (select Antigravity) -> "8"
        # Select Antigravity options: "1, 2" -> "1, 2"
        inputs = "\n\n8\n1, 2\n"
        
        env = dict(os.environ)
        env["HOME"] = self.tmp
        
        process = subprocess.Popen(
            [sys.executable, "cli.py", "setup"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        stdout, stderr = process.communicate(input=inputs, timeout=5)
        
        self.assertEqual(process.returncode, 0)
        self.assertIn("Antigravity", stdout)
        self.assertIn("Antigravity IDE", stdout)
        self.assertIn("Antigravity 2.0", stdout)
        
        # Ensure Antigravity CLI is not in the installed apps in the Live Dashboard
        live_section = stdout.split("Chronicle Environment Live")[1]
        self.assertNotIn("Antigravity CLI", live_section)

    def test_cli_setup_wizard_interactive_mocked(self):
        from unittest.mock import patch
        import cli
        
        # We mock getch to press:
        # Down (1), Space (toggle VS Code), Down (2), Down (3), Space (toggle Claude), Down (4), Down (5), Down (6), Space (toggle Antigravity), Down (7), Space (toggle Antigravity IDE), Enter (confirm)
        # Sequence of keys:
        # Down: '\x1b[B'
        # Space: ' '
        # Enter: '\n'
        mock_keys = [
            '\x1b[B', ' ',  # vscode toggled
            '\x1b[B', '\x1b[B', ' ',  # claude toggled
            '\x1b[B', '\x1b[B', '\x1b[B', '\x1b[B', ' ',  # antigravity toggled (now sub-options are visible!)
            '\x1b[B', ' ',  # antigravity-ide toggled
            '\n'
        ]
        
        with patch('cli.getch', side_effect=mock_keys), \
             patch('sys.stdin.isatty', return_value=True), \
             patch('sys.stdout.write'):
            
            result, custom_input = cli.select_apps_interactive()
            
            # Verify which items are checked
            checked_ids = [item["id"] for item in result if item["checked"]]
            self.assertIn("vscode", checked_ids)
            self.assertIn("claude", checked_ids)
            self.assertIn("antigravity", checked_ids)
            self.assertIn("antigravity-ide", checked_ids)
            self.assertNotIn("cursor", checked_ids)
            self.assertNotIn("antigravity-cli", checked_ids)

    def test_cli_setup_wizard_interactive_custom_input(self):
        from unittest.mock import patch, MagicMock
        import cli
        
        # Navigate down to other (9 times Down), type "myide", press Backspace, type "es", Enter
        mock_keys = [
            '\x1b[B', '\x1b[B', '\x1b[B', '\x1b[B', '\x1b[B', '\x1b[B', '\x1b[B', '\x1b[B', '\x1b[B', # Down 9 times
            'm', 'y', 'i', 'd', 'e', # type "myide"
            '\x7f', # Backspace (removes "e")
            'e', 's', # type "es"
            '\n' # Enter
        ]
        
        mock_path = MagicMock()
        mock_path.parent.exists.return_value = True
        
        with patch('cli.getch', side_effect=mock_keys), \
             patch('sys.stdin.isatty', return_value=True), \
             patch('cli.get_config_path', return_value=mock_path), \
             patch('sys.stdout.write'):
            
            result, custom_input = cli.select_apps_interactive()
            
            self.assertEqual(custom_input, "myides")

    def test_save_handoff_receipt(self):
        res = self.cc.save_handoff_receipt(
            obligations={"promise": "Fix all the failing unit tests", "scope": ["cli.py", "chat_core.py"]},
            work_state={
                "touched_surfaces": [{"file_path": "chat_core.py", "summary": "Changed naming of parts", "why": "Fix test assertions"}],
                "dependencies": ["twine"]
            },
            evidence={
                "checks_run": [{"command": "pytest", "exit_code": 0, "stdout_summary": "All passed"}],
                "missing_evidence": []
            },
            invalidation={
                "stale_if": [],
                "next_safe_action": "Publish new version"
            }
        )
        self.assertIn("Handoff receipt saved successfully", res)
        
        # Verify it exists in storage folder
        chats_dir = self.cc.resolve_chats_dir("default")
        files = os.listdir(chats_dir)
        handoff_files = [f for f in files if f.startswith("handoff_") and f.endswith(".json")]
        self.assertEqual(len(handoff_files), 1)
        
        # Verify content
        with open(os.path.join(chats_dir, handoff_files[0]), "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["obligations"]["promise"], "Fix all the failing unit tests")
        self.assertEqual(data["invalidation"]["next_safe_action"], "Publish new version")
        
        # Re-index
        self.cc._sync_serialized_index("default")
        
        # Search it
        hits = self.cc.search_history(query="failing unit tests", method="keyword")
        self.assertTrue(any("handoff_" in h for h in hits))

    def test_handoff_receipt_decay_and_deduplication(self):
        # Create standard chat (Doc 1) with specific keyword
        self._write_chat("standard_decay.json", [{"role": "user", "content": "receiptterm decay testing"}])
        # Create handoff receipts from the same workspace (Doc 2 and Doc 3)
        # Doc 2 is older (timestamp 1700000000)
        old_receipt_path = os.path.join(self.cc.resolve_chats_dir("default"), "handoff_1700000000_abcd1234.json")
        with open(old_receipt_path, "w", encoding="utf-8") as f:
            json.dump({
                "receipt_id": "abcd1234_1700000000",
                "status": "open",
                "obligations": {"promise": "old receiptterm promise", "scope": []},
                "work_state": {"touched_surfaces": [], "dependencies": []},
                "evidence": {"checks_run": [], "missing_evidence": []},
                "invalidation": {"stale_if": [], "next_safe_action": ""},
                "messages": [{"role": "assistant", "text": "receiptterm", "timestamp": 1700000000}],
                "timestamp": 1700000000
            }, f)
            
        # Doc 3 is newer (current time)
        import time
        now = int(time.time())
        new_receipt_path = os.path.join(self.cc.resolve_chats_dir("default"), f"handoff_{now}_abcd1234.json")
        with open(new_receipt_path, "w", encoding="utf-8") as f:
            json.dump({
                "receipt_id": f"abcd1234_{now}",
                "status": "open",
                "obligations": {"promise": "new receiptterm promise", "scope": []},
                "work_state": {"touched_surfaces": [], "dependencies": []},
                "evidence": {"checks_run": [], "missing_evidence": []},
                "invalidation": {"stale_if": [], "next_safe_action": ""},
                "messages": [{"role": "assistant", "text": "receiptterm", "timestamp": now}],
                "timestamp": now
            }, f)
            
        self.cc._sync_serialized_index("default")
        
        # 1. Verify Workspace Deduplication Gate:
        # Searching for 'receiptterm' should return 'handoff_<now>_abcd1234' but NOT 'handoff_1700000000_abcd1234'
        hits = self.cc.search_history(query="receiptterm", method="keyword")
        self.assertTrue(any(f"handoff_{now}_abcd1234" in h for h in hits))
        self.assertFalse(any("handoff_1700000000_abcd1234" in h for h in hits))

    def test_multi_agent_state_coherence_and_active_invalidation(self):
        import time
        import hashlib
        now = int(time.time())
        workspace_hash = hashlib.md5(self.cc.base_dir.encode("utf-8")).hexdigest()[:8]
        
        chats_dir = self.cc.resolve_chats_dir("default")
        receipt_path = os.path.join(chats_dir, f"handoff_{now}_{workspace_hash}.json")
        
        pkg_json_path = os.path.join(self.cc.base_dir, "package.json")
        with open(pkg_json_path, "w") as f:
            f.write("{}")
            
        os.utime(pkg_json_path, (now - 100, now - 100))
        
        with open(receipt_path, "w", encoding="utf-8") as f:
            json.dump({
                "receipt_id": f"{workspace_hash}_{now}",
                "supersedes": None,
                "status": "open",
                "obligations": {"promise": "Verify state coherence test", "scope": []},
                "work_state": {"touched_surfaces": [], "dependencies": []},
                "evidence": {
                    "checks_run": [],
                    "missing_evidence": ["npm run test"]
                },
                "closure": {},
                "invalidation": {
                    "stale_if": [{"file_path": "package.json"}],
                    "next_safe_action": "Run npm run test"
                },
                "messages": [{"role": "assistant", "text": "Verify state coherence test", "timestamp": now}],
                "timestamp": now
            }, f)
            
        state = self.cc.get_workspace_handoff_state("default")
        self.assertTrue(state["blocked"])
        self.assertEqual(state["next_safe_action"], "Run npm run test")
        
        self.cc._sync_serialized_index("default")
        hits = self.cc.search_history(query="coherence", method="keyword")
        self.assertTrue(any(f"handoff_{now}_{workspace_hash}" in h for h in hits))
        
        os.utime(pkg_json_path, (now + 100, now + 100))
        
        sem_hits = self.cc.search_history(query="coherence", method="semantic")
        receipt_hits = [h for h in sem_hits if f"handoff_{now}_{workspace_hash}" in h.get("file", "")]
        for h in receipt_hits:
            self.assertEqual(h["score"], 0.0)

    def test_cli_custom_discovery_and_paths(self):
        import cli
        # Verify find_executable_or_app detects standard system commands like python / python3 / bash / sh / cmd
        self.assertTrue(cli.find_executable_or_app("sh") or cli.find_executable_or_app("cmd") or cli.find_executable_or_app("python3") or cli.find_executable_or_app("bash"))
        # Verify fake app does not exist
        self.assertFalse(cli.find_executable_or_app("nonexistent_fake_app_xyz"))
        
        # Verify get_config_paths returns multiple paths for vscode / codex
        vscode_paths = cli.get_config_paths("vscode")
        self.assertGreater(len(vscode_paths), 1)
        self.assertTrue(any("cline_mcp_settings.json" in str(p) for p in vscode_paths))

        # Verify Windsurf config path resolves to codeium/windsurf/mcp_config.json
        windsurf_paths = cli.get_config_paths("windsurf")
        self.assertTrue(any(".codeium" in str(p) and "mcp_config.json" in str(p) for p in windsurf_paths))

        # Verify Trae config path resolves to .trae/mcp.json
        trae_paths = cli.get_config_paths("trae")
        self.assertTrue(any(".trae" in str(p) and "mcp.json" in str(p) for p in trae_paths))

    def test_security_containment_and_path_traversal(self):
        from chat_core import sanitize_filename, summarize_text_code_blocks
        
        # 1. sanitize_filename tests
        self.assertEqual(sanitize_filename("../../etc/passwd"), "etc_passwd")
        self.assertEqual(sanitize_filename("CON"), "_CON")
        self.assertEqual(sanitize_filename("aux.json"), "_aux.json")
        self.assertEqual(sanitize_filename("nul"), "_nul")
        self.assertEqual(sanitize_filename("   ...   "), "untitled")
        self.assertEqual(sanitize_filename("foo\x00bar"), "foobar")
        self.assertEqual(sanitize_filename(""), "untitled")

        # 2. _safe_chat_path path traversal blocks
        self.assertIsNone(self.cc._safe_chat_path("../../etc/passwd"))
        self.assertIsNone(self.cc._safe_chat_path("..\\..\\etc\\passwd"))
        self.assertIsNone(self.cc._safe_chat_path("C:\\Windows\\win.ini"))
        self.assertIsNone(self.cc._safe_chat_path("/etc/passwd"))
        self.assertIsNone(self.cc._safe_chat_path("evil\x00.json"))
        self.assertIsNone(self.cc._safe_chat_path("foo/../bar.json"))

        # 3. resolve_chats_dir boundary enforcement
        # Malicious client names or paths cannot escape base_dir
        self.cc.maintain_storage(op_type="configure", settings={
            "client_paths": {"evil": "../../etc", "abs": "/etc"}
        })
        self.assertNotIn("evil", self.cc.load_config().get("client_paths", {}))
        self.assertNotIn("abs", self.cc.load_config().get("client_paths", {}))
        
        resolved_evil = self.cc.resolve_chats_dir("../../escape")
        self.assertTrue(os.path.commonpath([resolved_evil, os.path.abspath(self.cc.base_dir)]) == os.path.abspath(self.cc.base_dir))

        # 4. import_chat_from_local_path outside boundary blocks
        blocked_import = self.cc.import_chat_from_local_path("/etc/hosts")
        self.assertIn("Access denied", blocked_import)

        # 5. Markdown export path containment
        self._write_chat("export_sec.json", [{"role": "user", "content": "hi"}])
        export_blocked = self.cc.export_chat_as_markdown("export_sec.json", output_name="../../escaped.md")
        self.assertNotIn("escaped.md", os.listdir(self.cc.base_dir))

        # 6. ReDoS resistance on code block summarization
        long_unmatched = "```python\n" + ("x" * 1000 + "\n") * 10
        summarized = summarize_text_code_blocks(long_unmatched)
        self.assertIn("Code Block", summarized)

    def test_security_staleness_probing_and_file_caps(self):
        from chat_core import _evaluate_stale_conditions, _resolve_active_receipt
        
        # 1. Host probing via stale_if outside workspace must be ignored
        receipt = {
            "timestamp": 0.0,
            "status": "open",
            "invalidation": {
                "stale_if": [{"file_path": "/etc/hosts"}, {"file_path": "../../sensitive.txt"}],
                "next_safe_action": "Do something"
            }
        }
        # /etc/hosts exists and is newer than 0.0, but outside base_dir/cwd, so it must NOT trigger stale condition
        self.assertFalse(_evaluate_stale_conditions(receipt, self.cc.base_dir))

        resolved = _resolve_active_receipt(receipt, self.cc.base_dir)
        self.assertEqual(resolved["status"], "open")
        self.assertEqual(resolved["invalidation"]["next_safe_action"], "Do something")

        # 2. String timestamps (ISO strings) must be handled safely without TypeError
        receipt_str_ts = {
            "timestamp": "2026-10-17T00:00:00Z",
            "status": "open",
            "invalidation": {
                "stale_if": [],
                "next_safe_action": "Proceed"
            }
        }
        self.assertFalse(_evaluate_stale_conditions(receipt_str_ts, self.cc.base_dir))

    def test_search_and_algorithmic_resilience(self):
        from chat_core import calculate_bm25_score, apply_temporal_decay, _chunk_conversation

        # 1. BM25 cross-client scoping & non-negative IDF
        term_freqs = {
            "search": {
                "client1/doc1.json": 2,
                "client2/doc2.json": 5,
                "client2/doc3.json": 3
            }
        }
        doc_lengths = {
            "client1/doc1.json": 10,
            "client2/doc2.json": 20,
            "client2/doc3.json": 15
        }
        # Client 1 only has 1 doc, but global term_freqs has 3 docs across all clients
        bm25_res = calculate_bm25_score(
            query_terms=["search"],
            doc_id="client1/doc1.json",
            term_frequencies=term_freqs,
            doc_lengths=doc_lengths,
            n_docs=1
        )
        self.assertGreater(bm25_res, 0.0)

        # 2. Temporal decay zero-timestamp underflow prevention
        self.assertEqual(apply_temporal_decay(1.5, 0.0), 1.5)
        self.assertEqual(apply_temporal_decay(1.5, -10.0), 1.5)

        # 3. Chunking with 'content' format instead of 'text'
        raw_msgs = [
            {"content": f"Message turn {i} about python architecture", "timestamp": 1000 + (i * 10)}
            for i in range(10)
        ]
        chunks = _chunk_conversation(raw_msgs)
        self.assertGreater(len(chunks), 0)

        # 4. Pagination bounds normalization in read_chat_message_range
        self._write_chat("page_test.json", [
            {"role": "user", "content": "turn 1"},
            {"role": "assistant", "content": "turn 2"}
        ])
        # Start message exceeds total
        res_exceed = self.cc.read_chat_message_range("page_test.json", start_msg=5, end_msg=10)
        self.assertIn("exceeds total messages", res_exceed)

        # Inverted range start > end should be normalized safely
        res_inverted = self.cc.read_chat_message_range("page_test.json", start_msg=2, end_msg=1)
        self.assertIn("Showing Messages 2 to 2", res_inverted)

        # 5. Deduplication in merge_conversation_into_archive
        self._write_chat("merge_dedup.json", [
            {"role": "user", "content": "first message"},
            {"role": "assistant", "content": "second message"}
        ])
        # Merging duplicates should not increase count
        dup_msgs = [
            {"role": "user", "content": "first message"},
            {"role": "assistant", "content": "second message"}
        ]
        merge_res1 = self.cc.merge_conversation_into_archive("merge_dedup.json", dup_msgs)
        self.assertIn("Merged 0 messages", merge_res1)
        self.assertIn("total: 2", merge_res1)

        # Merging one new message should result in total 3
        new_msg = [{"role": "user", "content": "third novel message"}]
        merge_res2 = self.cc.merge_conversation_into_archive("merge_dedup.json", new_msg)
        self.assertIn("Merged 1 messages", merge_res2)
        self.assertIn("total: 3", merge_res2)

        # 6. Float precision in handoff receipt timestamps
        self.cc.save_handoff_receipt(
            obligations={"promise": "Test", "scope": []},
            work_state={"touched_surfaces": [], "dependencies": []},
            evidence={"checks_run": [], "missing_evidence": []},
            invalidation={"stale_if": [], "next_safe_action": "Done"},
            status="open"
        )
        receipt_files = [f for f in os.listdir(self.cc.resolve_chats_dir("default")) if f.startswith("handoff_")]
        self.assertGreater(len(receipt_files), 0)
        with open(os.path.join(self.cc.resolve_chats_dir("default"), receipt_files[0]), "r") as f:
            rec_json = json.load(f)
            self.assertIsInstance(rec_json["timestamp"], float)

    def test_concurrency_and_storage_resilience(self):
        import concurrent.futures
        import cli
        from pathlib import Path

        # 1. Atomic write-and-replace prevents file truncation on error
        target_path = os.path.join(self.cc.chats_dir, "atomic_test.json")
        self.cc._write_json(target_path, {"initial": "data"})
        self.assertTrue(os.path.exists(target_path))
        with open(target_path, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"initial": "data"})

        # Attempt to write non-serializable object (triggers exception inside write)
        class Unserializable:
            pass

        with self.assertRaises(TypeError):
            self.cc._write_json(target_path, {"bad": Unserializable()})

        # Verify original file content is intact and not truncated
        with open(target_path, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"initial": "data"})

        # Verify no orphaned temp files remained
        tmp_files = [f for f in os.listdir(self.cc.chats_dir) if f.startswith(".tmp_chronicle_")]
        self.assertEqual(len(tmp_files), 0)

        # 2. Handoff receipt exclusion from gzip compression
        receipt_path = os.path.join(self.cc.chats_dir, "handoff_1234567890_abcdef12.json")
        with open(receipt_path, "w", encoding="utf-8") as f:
            json.dump({"receipt_id": "test"}, f)
        
        chat_path = os.path.join(self.cc.chats_dir, "normal_chat_archive.json")
        with open(chat_path, "w", encoding="utf-8") as f:
            json.dump({"title": "normal"}, f)

        # Set modification time older than 30 days
        past_60_days = time.time() - (60 * 86400)
        os.utime(receipt_path, (past_60_days, past_60_days))
        os.utime(chat_path, (past_60_days, past_60_days))

        comp_res = self.cc.compress_old_chat_archives(days_old=30)
        self.assertIn("normal_chat_archive.json", comp_res["compressed"])
        self.assertNotIn("handoff_1234567890_abcdef12.json", comp_res["compressed"])
        self.assertTrue(os.path.exists(receipt_path))
        self.assertFalse(os.path.exists(receipt_path + ".gz"))

        # 3. Thread-safe concurrent operations across ChatConnector
        def worker(thread_id):
            c_name = f"thread_chat_{thread_id}"
            msgs = [{"role": "user", "content": f"msg from thread {thread_id}"}]
            self.cc.save_current_conversation_state(c_name, msgs, force_save=True)
            self.cc.merge_conversation_into_archive(f"{c_name}.json", [{"role": "assistant", "content": "ack"}])
            self.cc._sync_serialized_index("default")
            self.cc.watch_chats_folder("default")
            return True

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        self.assertEqual(len(results), 10)

        # 4. Config overwrite safeguard in cli.py
        cfg_file = Path(self.cc.base_dir) / "corrupt_app_config.json"
        with open(cfg_file, "w", encoding="utf-8") as f:
            f.write("{ INVALID JSON CONTENT THAT WOULD BE WIPED")

        # Mock get_config_paths to return this corrupt file
        orig_get_paths = cli.get_config_paths
        try:
            cli.get_config_paths = lambda app: [cfg_file]
            cli.update_json_config("custom_test_app")
            # Verify backup was created
            bak_file = cfg_file.with_suffix(cfg_file.suffix + ".bak")
            self.assertTrue(bak_file.exists())
            with open(bak_file, "r", encoding="utf-8") as bf:
                self.assertIn("INVALID JSON", bf.read())
            # Verify cfg_file was repaired with valid JSON containing chronicle-mcp
            with open(cfg_file, "r", encoding="utf-8") as cf:
                data = json.load(cf)
                self.assertIn("chronicle-mcp", data.get("mcpServers", {}))
        finally:
            cli.get_config_paths = orig_get_paths

    def test_phase_4_comprehensive_hardening(self):
        # 1. Author string attribute handling without AttributeError
        msgs = [
            {"author": "user", "text": "hello from user"},
            {"author": "assistant", "content": "hello from assistant"},
        ]
        plain = parse_to_plain_text(msgs)
        self.assertEqual(plain, ["U: hello from user", "A: hello from assistant"])
        self.cc.save_current_conversation_state("str_author_test", msgs, force_save=True)
        merge_res = self.cc.merge_conversation_into_archive("str_author_test.json", msgs)
        self.assertIn("Merged", merge_res)

        # 2. Handoff DAG: Closed child superseding open parent resolves workspace block
        r1_res = self.cc.save_handoff_receipt(
            obligations={"promise": "Parent Task", "scope": ["test.py"]},
            work_state={"touched_surfaces": []},
            evidence={"checks_run": []},
            invalidation={"stale_if": [], "next_safe_action": "Fix parent"},
            status="open",
        )
        # The save result reports the receipt_id that 'supersedes' must reference.
        r1_id = r1_res.split("(receipt_id: ")[1].rstrip(")")

        # Child supersedes parent and is closed
        self.cc.save_handoff_receipt(
            obligations={"promise": "Child Task", "scope": ["test.py"]},
            work_state={"touched_surfaces": []},
            evidence={"checks_run": []},
            invalidation={"stale_if": []},
            status="closed",
            closure={
                "closed_by": "tester",
                "closed_at": "2026-10-17T12:00:00Z",
                "closure_basis": "verified resolved",
            },
            supersedes=r1_id,
        )

        state = self.cc.get_workspace_handoff_state("default")
        self.assertFalse(state["blocked"], "Closed child must resolve prior open parent obligation")
        self.assertIsNone(state["blocked_by_receipt"])

        # 3. Deduplicate removes deleted files from .chronicle_index.json
        payload = json.dumps({"title": "identical_chat", "messages": [{"role": "user", "content": "same content"}]})
        c1 = os.path.join(self.cc.resolve_chats_dir("default"), "orig_file.json")
        c2 = os.path.join(self.cc.resolve_chats_dir("default"), "dup_file.json")
        with open(c1, "w", encoding="utf-8") as f:
            f.write(payload)
        with open(c2, "w", encoding="utf-8") as f:
            f.write(payload)
        self.cc._sync_serialized_index("default")
        idx_before = self.cc._load_serialized_index()
        self.assertIn("default/dup_file__part_1.json", idx_before.get("doc_lengths", {}))

        dedup_res = self.cc.deduplicate_stored_chats(dry_run=False, client="default")
        self.assertEqual(len(dedup_res["duplicates"]), 1)
        removed_file = dedup_res["duplicates"][0]["file"]
        self.assertFalse(os.path.exists(os.path.join(self.cc.resolve_chats_dir("default"), removed_file)))

        idx_after = self.cc._load_serialized_index()
        stem = removed_file.replace(".json", "")
        self.assertNotIn(f"default/{stem}__part_1.json", idx_after.get("doc_lengths", {}))

        # 4. Sandboxing sync_agent_transcripts against unauthorized source_dir
        sync_denied = self.cc.sync_agent_transcripts("cursor", source_dir="/etc")
        self.assertIn("Access denied", sync_denied.get("error", ""))

        # 5. CLI discover_config_files_by_content handles invalid JSON without TypeError
        inv_dir = Path(self.tmp) / "search_test"
        inv_dir.mkdir(parents=True, exist_ok=True)
        sub_dir = inv_dir / "testapp"
        sub_dir.mkdir(parents=True, exist_ok=True)
        with open(sub_dir / "broken.json", "w", encoding="utf-8") as f:
            f.write("CORRUPT JSON NOT A DICT")
        found = cli.discover_config_files_by_content("testapp", [inv_dir])
        self.assertEqual(found, [])

        # 6. CLI split_export_file path traversal containment and collision handling
        exp_file = Path(self.tmp) / "export_test.json"
        out_split = Path(self.tmp) / "split_out"
        with open(exp_file, "w", encoding="utf-8") as f:
            json.dump([
                {"title": "../../sneaky_traversal", "messages": []},
                {"title": "Dup Title", "messages": []},
                {"title": "Dup Title", "messages": []},
            ], f)
        cli.split_export_file(exp_file, out_split)
        self.assertTrue((out_split / "____sneaky_traversal.json").exists() or (out_split / "sneaky_traversal.json").exists())
        self.assertTrue((out_split / "Dup Title.json").exists() or (out_split / "Dup_Title.json").exists())
        self.assertTrue((out_split / "Dup Title_1.json").exists() or (out_split / "Dup_Title_1.json").exists())


if __name__ == "__main__":
    unittest.main()

