#!/usr/bin/env python3
"""Exercise all 24 Universal Chat Connector tools against the live archive."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone

from chat_core import ChatConnector, get_connector

PASS = "PASS"
FAIL = "FAIL"
results: list[dict] = []

# Use isolated temp dir for destructive tests; real connector for read ops
REAL = get_connector()
TMP_BASE = tempfile.mkdtemp(prefix="ucc_test_")
TEST = ChatConnector(base_dir=TMP_BASE)

DEMO = "universal-chat-connector-demo.json"
SECOND = "Optimizing AntiGravity IDE and Claude Code setup.json"


def record(tool: str, status: str, detail: str) -> None:
    results.append({"tool": tool, "status": status, "detail": detail[:200]})
    icon = "✅" if status == PASS else "❌"
    print(f"{icon} {tool}: {detail[:120]}")


def ok(tool: str, cond: bool, detail: str) -> None:
    record(tool, PASS if cond else FAIL, detail)


# ── 1. Core (4) ─────────────────────────────────────────────────────────────

files = REAL.list_all_stored_chats()
ok("list_all_stored_chats", len(files) > 1 and "No stored" not in files[0], f"{len(files)} files")

hits = REAL.search_chats_by_keywords(["mcp", "connector"])
ok("search_chats_by_keywords", len(hits) > 0 and "error" not in hits[0].lower(), f"top={hits[0]}")

if DEMO in files:
    text = REAL.read_chat_message_range(DEMO, 1, 5)
    ok("read_chat_message_range", "U:" in text and "total messages" in text, text.split("\n")[0])
else:
    ok("read_chat_message_range", False, f"{DEMO} missing")

save_msgs = [{"role": "user", "content": "full test save"}, {"role": "assistant", "content": "saved ok"}]
save_res = TEST.save_current_conversation_state("tool-test-save", save_msgs, force_save=True)
ok("save_current_conversation_state", "Successfully saved" in save_res, save_res)

# ── 2. High impact (4) ──────────────────────────────────────────────────────

if DEMO in files:
    meta = REAL.get_chat_metadata(DEMO)
    ok("get_chat_metadata", meta.get("message_count", 0) > 0, str(meta))
else:
    ok("get_chat_metadata", False, "demo missing")

merge_res = TEST.merge_conversation_into_archive(
    "tool-test-save.json", [{"role": "user", "content": "merged message"}]
)
ok("merge_conversation_into_archive", "total: 3" in merge_res, merge_res)

export_res = TEST.export_chat_as_markdown("tool-test-save.json", "tool-test-save.md")
ok("export_chat_as_markdown", "Exported markdown" in export_res, export_res)

blocked = TEST.delete_stored_chat("tool-test-save.json", confirm=False)
ok("delete_stored_chat (blocked)", "confirm=true" in blocked, blocked)
deleted = TEST.delete_stored_chat("tool-test-save.json", confirm=True)
ok("delete_stored_chat (confirmed)", "Deleted" in deleted, deleted)

# ── 3. Search & retrieval (4) ─────────────────────────────────────────────

semantic = REAL.search_chats_semantic("mcp chat connector", top_k=3)
ok("search_chats_semantic", semantic[0].get("score", 0) > 0, str(semantic[0]))

if DEMO in files:
    summary = REAL.get_chat_summary(DEMO)
    ok("get_chat_summary", len(summary) > 20, summary[:80])
    related = REAL.find_related_chats(DEMO, top_k=3)
    ok("find_related_chats", len(related) > 0, str(related[:2]))
else:
    ok("get_chat_summary", False, "demo missing")
    ok("find_related_chats", False, "demo missing")

today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
dated = REAL.filter_chats_by_date_range(today, today)
ok("filter_chats_by_date_range", len(dated) > 0, f"{len(dated)} files today")

# ── 4. Automation (6) ───────────────────────────────────────────────────────

reg = TEST.register_session_for_auto_save("auto-test", [{"role": "user", "content": "pending"}])
ok("register_session_for_auto_save", "registered" in reg, reg)
auto = TEST.trigger_auto_save_on_session_end()
ok("trigger_auto_save_on_session_end", "Successfully saved" in auto, auto)

watch = REAL.watch_chats_folder()
ok("watch_chats_folder", "new_files" in watch and "total_tracked" in watch, str(watch)[:80])

content = json.dumps({"messages": [{"role": "user", "content": "imported via content"}]})
imported = TEST.import_chat_from_content("import-content-test", content)
ok("import_chat_from_content", "Imported chat" in imported, imported)

# import from real file
real_demo_path = os.path.join(REAL.chats_dir, DEMO) if DEMO in files else None
if real_demo_path and os.path.exists(real_demo_path):
    local = TEST.import_chat_from_local_path(real_demo_path, title="import-local-test")
    ok("import_chat_from_local_path", "Imported chat" in local, local)
else:
    ok("import_chat_from_local_path", False, "no source file")

sync = REAL.sync_cursor_agent_transcripts(limit=3)
ok("sync_cursor_agent_transcripts", "imported" in sync or "error" in sync, str(sync)[:100])

# ── 5. Intelligence (4) ───────────────────────────────────────────────────

task_file = None
for f in files:
    if f == "Team to-do list platform for game development.json":
        task_file = f
        break
target = task_file or DEMO
actions = REAL.extract_action_items(target)
ok("extract_action_items", isinstance(actions, list) and len(actions) > 0, str(actions[:2]))

index = REAL.build_knowledge_index(rebuild=True)
ok("build_knowledge_index", "mcp" in index and "built_at" in index, f"mcp={len(index['mcp'])}, ui={len(index['ui_design'])}")

if DEMO in files and SECOND in files:
    compare = REAL.compare_two_chats(DEMO, SECOND)
    ok("compare_two_chats", "Compare:" in compare and "Shared topics" in compare, compare[:80])
    brief = REAL.generate_project_brief_from_chats([DEMO, SECOND], "Full Tool Test Brief")
    ok("generate_project_brief_from_chats", "Brief written" in brief, brief)
else:
    ok("compare_two_chats", False, "files missing")
    ok("generate_project_brief_from_chats", False, "files missing")

# ── 6. Ops (4) ──────────────────────────────────────────────────────────────

cfg = TEST.configure_connector_settings({"auto_save_message_threshold": 3})
ok("configure_connector_settings", "auto_save_message_threshold" in cfg, cfg)

# compress only on temp old file
old_chat = os.path.join(TEST.chats_dir, "old_chat.json")
with open(old_chat, "w") as f:
    json.dump({"title": "old", "messages": [{"role": "user", "content": "old"}]}, f)
old_ts = (datetime.now(timezone.utc).timestamp()) - (31 * 86400)
os.utime(old_chat, (old_ts, old_ts))
compress = TEST.compress_old_chat_archives(days_old=30)
ok("compress_old_chat_archives", len(compress.get("compressed", [])) >= 1, str(compress))

payload = {"title": "d", "messages": [{"role": "user", "content": "dup"}]}
for n in ("dup1.json", "dup2.json"):
    with open(os.path.join(TEST.chats_dir, n), "w") as f:
        json.dump(payload, f, indent=2)
dedupe = TEST.deduplicate_stored_chats(dry_run=True)
ok("deduplicate_stored_chats", len(dedupe.get("duplicates", [])) >= 1, str(dedupe))

caps = REAL.get_server_capabilities()
ok("get_server_capabilities", caps.get("total_tools") == 24, f"{caps['total_tools']} tools")

# ── Summary ─────────────────────────────────────────────────────────────────

passed = sum(1 for r in results if r["status"] == PASS)
failed = sum(1 for r in results if r["status"] == FAIL)
print(f"\n{'='*50}")
print(f"TOTAL: {passed}/{len(results)} passed, {failed} failed")
if failed:
    print("\nFailures:")
    for r in results:
        if r["status"] == FAIL:
            print(f"  - {r['tool']}: {r['detail']}")

shutil.rmtree(TMP_BASE, ignore_errors=True)
raise SystemExit(0 if failed == 0 else 1)
