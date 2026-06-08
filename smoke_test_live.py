#!/usr/bin/env python3
"""Live smoke test against the real chats/ archive (read-only ops)."""

from chat_core import get_connector

cc = get_connector()
results: list[str] = []

# Core
files = cc.list_all_stored_chats()
results.append(f"list: {len(files)} files")

hits = cc.search_chats_by_keywords(["mcp", "connector"])
results.append(f"keyword search: {len(hits)} hits, top={hits[0] if hits else 'none'}")

# High impact (read-only)
demo = "universal-chat-connector-demo.json"
if demo in files:
    meta = cc.get_chat_metadata(demo)
    results.append(f"metadata: {meta.get('message_count')} msgs, {meta.get('file_size_bytes')} bytes")
    export = cc.export_chat_as_markdown(demo, "universal-chat-connector-demo.md")
    results.append(f"export: {export}")

# Search & retrieval
semantic = cc.search_chats_semantic("mcp chat connector archive", top_k=3)
results.append(f"semantic top: {semantic[0] if semantic else 'none'}")
summary = cc.get_chat_summary(demo) if demo in files else "n/a"
results.append(f"summary: {summary[:80]}...")
today = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d")
dated = cc.filter_chats_by_date_range(today, today)
results.append(f"date filter today: {len(dated)} files")

# Automation
watch = cc.watch_chats_folder()
results.append(f"watch: new={len(watch['new_files'])}, modified={len(watch['modified_files'])}")

# Intelligence
index = cc.build_knowledge_index(rebuild=True)
results.append(f"index topics: mcp={len(index.get('mcp', []))}, ui={len(index.get('ui_design', []))}")
if demo in files:
    actions = cc.extract_action_items(demo)
    results.append(f"actions: {actions}")

# Ops
caps = cc.get_server_capabilities()
results.append(f"capabilities: {caps['total_tools']} tools")
dedupe = cc.deduplicate_stored_chats(dry_run=True)
results.append(f"dedupe dry-run: {len(dedupe['duplicates'])} duplicates of {dedupe['unique_count']} unique")

print("\n".join(results))
print("\n✅ Live smoke test complete.")
