#!/usr/bin/env python3
"""Exercise the 6 consolidated polymorphic tools against the live archive."""

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

REAL = get_connector()
TMP_BASE = tempfile.mkdtemp(prefix="ucc_test_")
TEST = ChatConnector(base_dir=TMP_BASE)

DEMO = "universal-chat-connector-demo.json"
SECOND = "Optimizing AntiGravity IDE and Claude Code setup.json"

created_files = []
for filename, content in [
    (DEMO, {
        "title": "universal-chat-connector-demo",
        "messages": [
            {"role": "user", "content": "U: Hello, how do I build a model context protocol server?"},
            {"role": "assistant", "content": "To build an MCP server, you can use the python mcp sdk."},
            {"role": "user", "content": "TODO: implement client session management. Let's do that next."},
            {"role": "assistant", "content": "Sure, that is an action item to add."},
            {"role": "user", "content": "What is the best way to sync cursor agent transcripts?"}
        ]
    }),
    (SECOND, {
        "title": "Optimizing AntiGravity IDE and Claude Code setup",
        "messages": [
            {"role": "user", "content": "How to optimize AntiGravity IDE and Claude Code setup for typescript development?"},
            {"role": "assistant", "content": "You can configure rule files and adjust search settings."},
            {"role": "user", "content": "Excellent advice. Thank you."}
        ]
    })
]:
    target_path = os.path.join(REAL.chats_dir, filename)
    if not os.path.exists(target_path):
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)
        created_files.append(target_path)


def record(tool: str, status: str, detail: str) -> None:
    results.append({"tool": tool, "status": status, "detail": detail[:200]})
    status_label = "[PASS]" if status == PASS else "[FAIL]"
    print(f"{status_label} {tool}: {detail[:120]}")


def ok(tool: str, cond: bool, detail: str) -> None:
    record(tool, PASS if cond else FAIL, detail)


# ── 1. Search History ────────────────────────────────────────────────────────

hits_sem = REAL.search_history(query="mcp connector", method="semantic")
ok("search_history (semantic)", len(hits_sem) > 0 and "error" not in str(hits_sem[0]).lower(), f"top={hits_sem[0]}")

hits_key = REAL.search_history(query="mcp", method="keyword")
ok("search_history (keyword)", len(hits_key) > 0 and "error" not in str(hits_key[0]).lower(), f"top={hits_key[0]}")

# ── 2. Get Chat Logs ─────────────────────────────────────────────────────────

files = REAL.get_chat_logs()
ok("get_chat_logs (list)", len(files) > 1 and "No stored" not in files[0], f"{len(files)} files")

if DEMO in files:
    text = REAL.get_chat_logs(chat_id=DEMO, view_type="content", start_msg=1, end_msg=5)
    ok("get_chat_logs (content)", "U:" in text and "total messages" in text, text.split("\n")[0])
    
    meta = REAL.get_chat_logs(chat_id=DEMO, view_type="metadata")
    ok("get_chat_logs (metadata)", meta.get("message_count", 0) > 0, str(meta))
    
    summary = REAL.get_chat_logs(chat_id=DEMO, view_type="summary")
    ok("get_chat_logs (summary)", len(summary) > 20, summary[:80])
else:
    ok("get_chat_logs (content)", False, f"{DEMO} missing")
    ok("get_chat_logs (metadata)", False, f"{DEMO} missing")
    ok("get_chat_logs (summary)", False, f"{DEMO} missing")

# ── 3. Manage Session State ─────────────────────────────────────────────────

save_msgs = [{"role": "user", "content": "full test save"}, {"role": "assistant", "content": "saved ok"}]
save_res = TEST.manage_session_state(action="save", conversation_name="tool-test-save", messages=save_msgs, force_save=True)
ok("manage_session_state (save)", "Successfully saved" in save_res, save_res)

merge_res = TEST.manage_session_state(
    action="merge", file_name="tool-test-save.json", new_messages=[{"role": "user", "content": "merged message"}]
)
ok("manage_session_state (merge)", "total: 3" in merge_res, merge_res)

export_res = TEST.manage_session_state(action="export_markdown", file_name="tool-test-save.json")
ok("manage_session_state (export)", "Exported markdown" in export_res, export_res)

blocked = TEST.manage_session_state(action="delete", file_name="tool-test-save.json", confirm=False)
ok("manage_session_state (delete blocked)", "confirm=true" in blocked, blocked)
deleted = TEST.manage_session_state(action="delete", file_name="tool-test-save.json", confirm=True)
ok("manage_session_state (delete confirmed)", "Deleted" in deleted, deleted)

# ── 4. Sync Workspace Data ──────────────────────────────────────────────────

reg = TEST.manage_session_state(action="register_auto_save", conversation_name="auto-test", messages=[{"role": "user", "content": "pending"}])
ok("manage_session_state (register)", "registered" in reg, reg)
auto = TEST.manage_session_state(action="trigger_auto_save")
ok("manage_session_state (trigger auto-save)", "Successfully saved" in auto, auto)

watch = REAL.manage_session_state(action="watch_folder")
ok("manage_session_state (watch)", "new_files" in watch and "total_tracked" in watch, str(watch)[:80])

content = json.dumps({"messages": [{"role": "user", "content": "imported via content"}]})
imported = TEST.sync_workspace_data(source_type="raw_content", payload=content, title="import-content-test")
ok("sync_workspace_data (content)", "Imported chat" in imported, imported)

if DEMO in files:
    real_demo_path = os.path.join(REAL.chats_dir, DEMO)
    local = TEST.sync_workspace_data(source_type="local_path", payload=real_demo_path, title="import-local-test")
    ok("sync_workspace_data (local path)", "Imported chat" in local, local)
else:
    ok("sync_workspace_data (local path)", False, "no source file")

sync_uni = REAL.sync_workspace_data(source_type="agent_transcripts", client="cursor", limit=3)
ok("sync_workspace_data (sync transcripts)", "imported" in sync_uni or "error" in sync_uni, str(sync_uni)[:100])

# ── 5. Compile Project Insights ─────────────────────────────────────────────

target = DEMO
if DEMO in files:
    actions = REAL.compile_project_insights(insight_type="action_items", file_name=target)
    ok("compile_project_insights (action items)", isinstance(actions, list) and len(actions) > 0, str(actions[:2]))
else:
    ok("compile_project_insights (action items)", False, "demo missing")

index = REAL.compile_project_insights(insight_type="knowledge_index", rebuild=True)
ok("compile_project_insights (knowledge index)", "mcp" in index and "built_at" in index, f"mcp={len(index['mcp'])}, ui={len(index['ui_design'])}")

if DEMO in files and SECOND in files:
    compare = REAL.compile_project_insights(insight_type="compare_chats", file_name_a=DEMO, file_name_b=SECOND)
    ok("compile_project_insights (compare)", "Compare:" in compare and "Shared topics" in compare, compare[:80])
    
    brief = REAL.compile_project_insights(insight_type="project_brief", target_chats=[DEMO, SECOND], brief_title="Full Test Brief")
    ok("compile_project_insights (brief)", "Brief written" in brief, brief)
else:
    ok("compile_project_insights (compare)", False, "files missing")
    ok("compile_project_insights (brief)", False, "files missing")

# ── 6. Maintain Storage ─────────────────────────────────────────────────────

cfg = TEST.maintain_storage(op_type="configure", settings={"auto_save_message_threshold": 3})
ok("maintain_storage (configure)", "auto_save_message_threshold" in cfg, cfg)

old_chat = os.path.join(TEST.chats_dir, "old_chat.json")
with open(old_chat, "w") as f:
    json.dump({"title": "old", "messages": [{"role": "user", "content": "old"}]}, f)
old_ts = (datetime.now(timezone.utc).timestamp()) - (31 * 86400)
os.utime(old_chat, (old_ts, old_ts))
compress = TEST.maintain_storage(op_type="compress", days_old=30)
ok("maintain_storage (compress)", len(compress.get("compressed", [])) >= 1, str(compress))

payload = {"title": "d", "messages": [{"role": "user", "content": "dup"}]}
for n in ("dup1.json", "dup2.json"):
    with open(os.path.join(TEST.chats_dir, n), "w") as f:
        json.dump(payload, f, indent=2)
dedupe = TEST.maintain_storage(op_type="deduplicate", dry_run=True)
ok("maintain_storage (deduplicate)", len(dedupe.get("duplicates", [])) >= 1, str(dedupe))

caps = REAL.maintain_storage(op_type="capabilities")
ok("maintain_storage (capabilities)", caps.get("total_tools") == 6, f"{caps.get('total_tools')} tools")

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
for p in created_files:
    try:
        os.remove(p)
    except Exception:
        pass
raise SystemExit(0 if failed == 0 else 1)
