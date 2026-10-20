"""Chronicle MCP stdio server: tool, prompt and resource definitions.

All behavior lives in ``chat_core.ChatConnector``; this module only defines what
MCP clients see (names, titles, descriptions, parameter schemas, annotations)
and turns error-shaped results into proper ``isError`` tool results.
"""

from __future__ import annotations

import json
import os
import re
from typing import Annotated, Any, Literal

# pydantic requires typing_extensions.TypedDict on Python < 3.12.
from typing_extensions import TypedDict

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import Icon, ToolAnnotations
from pydantic import Field

from chat_core import __version__, get_connector

SERVER_NAME = "Chronicle MCP"

INSTRUCTIONS = """\
Chronicle is a local, private archive of the user's past AI chat transcripts (Cursor, Claude, ChatGPT, \
Cline and others), searchable with BM25. Nothing leaves the machine.

Typical flow:
1. Recall: search_history(query=...) to find relevant past chats; results are chunk ids like \
"name__part_2.json" with scores.
2. Read: get_chat_logs(chat_id=..., view_type="summary" or "content") with small message ranges to save tokens.
3. Save: manage_session_state(action="register_auto_save" or "save") to archive the current conversation.
4. Import: sync_workspace_data to pull in editor transcripts or exported chats.
5. Hand off: get_handoff_status at the start of work on a project, save_handoff_receipt before stopping.

Use compile_project_insights for derived output (action items, comparisons, briefs) and maintain_storage \
for housekeeping. Destructive operations require explicit flags (confirm=true, dry_run=false).
The 'client' parameter selects an archive namespace (subfolder); omit it to use "default".
"""

mcp = FastMCP(
    SERVER_NAME,
    instructions=INSTRUCTIONS,
    website_url="https://github.com/Leviathan0x0/Chronicle-MCP",
    icons=[
        Icon(
            src="https://raw.githubusercontent.com/Leviathan0x0/Chronicle-MCP/main/assets/logo.png",
            mimeType="image/png",
        )
    ],
    log_level=os.environ.get("CHRONICLE_LOG_LEVEL", "WARNING").upper(),  # type: ignore[arg-type]
)
# FastMCP does not take a version; without this serverInfo.version reports the mcp SDK version.
mcp._mcp_server.version = __version__
cc = get_connector()


def _evaluate_stale_conditions(receipt_data: dict, base_dir: str) -> bool:
    """
    Monitors file modifications relative to the receipt creation time.
    Returns True if any file in invalidation.stale_if is newer than the receipt timestamp.
    """
    from chat_core import _evaluate_stale_conditions as core_eval
    return core_eval(receipt_data, base_dir)


def _resolve_active_receipt(receipt_data: dict, base_dir: str) -> dict:
    """
    Catches stale states, intercepts the payload, and dynamically mutates
    both the status to 'blocked/stale' and the next_safe_action prompt.
    """
    from chat_core import _resolve_active_receipt as core_resolve
    return core_resolve(receipt_data, base_dir)


# ── Error handling ──────────────────────────────────────────────────────────

_ERROR_TEXT = re.compile(
    r"^(Error\b|[A-Z][a-z]+ error:|File .+ not found|Source path not found"
    r"|One or both files not found|No valid settings|Requested start message .+ exceeds)"
)


def _is_error_text(value: Any) -> bool:
    return isinstance(value, str) and bool(_ERROR_TEXT.match(value.strip()))


def _fail(message: Any) -> ToolError:
    # FastMCP prefixes "Error executing tool <name>: ", so drop a duplicate "Error: ".
    text = str(message).strip()
    return ToolError(text[len("Error: "):] if text.startswith("Error: ") else text)


def _checked(result: Any) -> Any:
    """Raise ToolError (an ``isError: true`` result) for error-shaped core results.

    ChatConnector reports failures as strings or ``{"error": ...}`` payloads so its
    Python API stays simple; MCP clients need them flagged as errors instead.
    """
    if _is_error_text(result):
        raise _fail(result)
    if isinstance(result, list) and len(result) == 1:
        item = result[0]
        if _is_error_text(item):
            raise _fail(item)
        if isinstance(item, dict):
            if "error" in item and len(item) == 1:
                raise _fail(item["error"])
            if _is_error_text(item.get("file")) and not item.get("score"):
                raise _fail(item["file"])
    if isinstance(result, dict) and "error" in result:
        others = [v for k, v in result.items() if k != "error"]
        if not any(others):
            raise _fail(result["error"])
    return result


# ── Shared parameter types ──────────────────────────────────────────────────

Client = Annotated[
    str,
    Field(
        description=(
            "Archive namespace (a subfolder of the chats directory). Built-in: 'default', 'cursor', "
            "'chatgpt', 'claude'; any other name creates its own subfolder. Omit to use 'default'."
        )
    ),
]
MessageList = Annotated[
    list[dict[str, Any]] | None,
    Field(
        description=(
            "Chat messages as objects with 'role' ('user', 'assistant' or 'system') and 'content' "
            "(text). 'text' is accepted in place of 'content'; extra keys such as 'timestamp' are kept."
        )
    ),
]

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


# ── Core tools ──────────────────────────────────────────────────────────────


@mcp.tool(
    title="Search Chat History",
    annotations=READ_ONLY,
    description=(
        "Search the local chat archive and return matching transcript chunks. Use this first to recall "
        "past work on a topic; then read a hit with get_chat_logs. For extracted action items, comparisons "
        "or briefs use compile_project_insights instead.\n"
        "Methods: 'semantic' (default) ranks chunks with Okapi BM25 plus recency decay and returns "
        "[{file, score}]; 'keyword' returns chunk ids containing every keyword; 'date_range' returns "
        "[{file_name, last_modified}] for chats saved between start_date and end_date; 'related' returns "
        "[{file, score}] for chats similar to file_name.\n"
        "Chunk ids look like 'name__part_2.json' and can be passed to get_chat_logs as chat_id. Active "
        "handoff receipts are ranked first. Read-only for chat data; it refreshes the local search index "
        "cache. An empty archive returns a single placeholder entry such as 'No stored chats found.'."
    ),
)
def search_history(
    query: Annotated[
        str,
        Field(description="Free-text query for 'semantic' search; for 'keyword' it is split on spaces when 'keywords' is omitted."),
    ] = "",
    method: Annotated[
        Literal["semantic", "keyword", "date_range", "related"],
        Field(description="Search strategy (see the tool description)."),
    ] = "semantic",
    keywords: Annotated[
        list[str] | None,
        Field(description="Exact terms for method='keyword'; all must appear. Overrides 'query' for that method."),
    ] = None,
    start_date: Annotated[
        str | None,
        Field(description="Inclusive start date (YYYY-MM-DD, UTC) for method='date_range'. Required with end_date."),
    ] = None,
    end_date: Annotated[
        str | None,
        Field(description="Inclusive end date (YYYY-MM-DD, UTC) for method='date_range'. Required with start_date."),
    ] = None,
    limit: Annotated[
        int, Field(ge=1, description="Maximum results for 'keyword' and 'date_range' searches.")
    ] = 50,
    top_k: Annotated[
        int, Field(ge=1, description="Maximum results for 'semantic' and 'related' searches.")
    ] = 10,
    client: Client = "default",
    file_name: Annotated[
        str | None,
        Field(description="Reference chat file for method='related' (for example 'my-chat.json'). Falls back to 'query'."),
    ] = None,
) -> list[str] | list[dict]:
    return _checked(cc.search_history(
        query=query,
        method=method,
        keywords=keywords,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        top_k=top_k,
        client=client,
        file_name=file_name,
    ))


@mcp.tool(
    title="Read Chat Logs",
    annotations=READ_ONLY,
    description=(
        "List archived chats, or read one chat as a message range, a short summary, or metadata. Use it "
        "after search_history to open a hit, or with no chat_id to browse the archive page by page. To "
        "search by topic use search_history instead.\n"
        "Without chat_id: returns a page header '[Page N of M (Total chats: T)]' followed by file names. "
        "With chat_id: view_type 'content' returns messages start_msg..end_msg as plain text with a "
        "'... of N total' header, truncating each message to max_msg_len characters and collapsing code "
        "blocks to one-line summaries unless summarize_code=false; 'summary' returns the opener and closer; "
        "'metadata' returns {file_name, title, message_count, file_size_bytes, last_modified, saved_at, client}. "
        "Older chats are shown pruned to save tokens. Keep ranges small (the default is 20 messages): "
        "max_msg_len=0 with a wide range can return a whole transcript. Read-only."
    ),
)
def get_chat_logs(
    chat_id: Annotated[
        str | None,
        Field(description="Chat file or chunk id to read, such as 'my-chat.json' or 'my-chat__part_2.json'. Omit to list chats."),
    ] = None,
    view_type: Annotated[
        Literal["content", "metadata", "summary"],
        Field(description="What to return for chat_id: message text ('content'), file statistics ('metadata') or a short 'summary'."),
    ] = "content",
    start_msg: Annotated[int, Field(ge=1, description="First message to return (1-based) for view_type='content'.")] = 1,
    end_msg: Annotated[int, Field(ge=1, description="Last message to return (inclusive) for view_type='content'.")] = 20,
    max_msg_len: Annotated[
        int, Field(ge=0, description="Per-message character cap for view_type='content'; 0 means no cap (can be very large).")
    ] = 1000,
    summarize_code: Annotated[
        bool, Field(description="Replace fenced code blocks with a one-line language and line-count summary to save tokens.")
    ] = True,
    page: Annotated[int, Field(ge=1, description="Page number (1-based) when listing chats without chat_id.")] = 1,
    per_page: Annotated[int, Field(ge=1, description="Chats per page when listing without chat_id.")] = 50,
    client: Client = "default",
) -> str | list[str] | dict:
    return _checked(cc.get_chat_logs(
        chat_id=chat_id,
        view_type=view_type,
        start_msg=start_msg,
        end_msg=end_msg,
        max_msg_len=max_msg_len,
        summarize_code=summarize_code,
        page=page,
        per_page=per_page,
        client=client,
    ))


@mcp.tool(
    title="Import Chats",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
    description=(
        "Import conversations into the archive from pasted content, a local file, or an editor's transcript "
        "folder, normalizing ChatGPT, Claude, Cline/Continue JSON, JSONL and Markdown formats. Use it to bring "
        "outside history in; to save the current conversation use manage_session_state(action='save').\n"
        "source_type 'raw_content': payload is the chat JSON (string or object); 'local_path': payload is a "
        "file path inside the archive, the current directory, the temp directory or a configured transcripts "
        "folder (other paths are refused); 'agent_transcripts': scans the transcripts folder for 'client' "
        "('cursor', 'continue', 'cline', 'copilot', or source_dir) and imports up to 'limit' newest files, "
        "skipping ones already imported; 'cursor_agent_transcripts' is a deprecated alias for Cursor.\n"
        "Writes new JSON files into the archive and updates the search index; never deletes. Imports with "
        "an existing title overwrite that chat. Returns a confirmation string for single imports, or "
        "{imported: [{file, status, dest}], errors, total_scanned} for folder syncs."
    ),
)
def sync_workspace_data(
    source_type: Annotated[
        Literal["agent_transcripts", "cursor_agent_transcripts", "local_path", "raw_content"],
        Field(description="Where to import from (see the tool description)."),
    ],
    payload: Annotated[
        str | dict | list | None,
        Field(description="Chat JSON for 'raw_content', a file path for 'local_path', or a folder path for 'agent_transcripts' (same as source_dir)."),
    ] = None,
    title: Annotated[
        str | None,
        Field(description="Archive name for 'raw_content' or 'local_path' imports. Defaults to a timestamped or source-derived name."),
    ] = None,
    source_dir: Annotated[
        str | None,
        Field(description="Override folder to scan for 'agent_transcripts'; must be inside an allowed root."),
    ] = None,
    limit: Annotated[int, Field(ge=1, description="Maximum newest transcript files to scan for folder syncs.")] = 50,
    client: Annotated[
        str,
        Field(
            description=(
                "Archive namespace to import into; for 'agent_transcripts' it also picks the source editor "
                "('cursor', 'continue', 'cline', 'copilot'). Omit for 'default'."
            )
        ),
    ] = "default",
) -> dict | str:
    return _checked(cc.sync_workspace_data(
        source_type=source_type,
        payload=payload,
        title=title,
        source_dir=source_dir,
        limit=limit,
        client=client,
    ))


@mcp.tool(
    title="Compile Project Insights",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
    description=(
        "Derive structured insight from archived chats: action items, a topic index, a two-chat comparison, "
        "or a Markdown project brief. Use it when you need a digest rather than raw text; to find chats use "
        "search_history and to read them use get_chat_logs.\n"
        "insight_type 'action_items': TODOs, checkboxes and 'next' tasks from file_name (or the first of "
        "target_chats), returned as a list of strings. 'knowledge_index': chats grouped by topic, returned as "
        "{topic: [files], built_at}, or file counts when summary_only=true (use that on large archives); "
        "rebuild=true rescans every file. 'compare_chats': shared and unique topics of file_name_a and "
        "file_name_b (or the first two target_chats) as Markdown. 'project_brief': merges summaries and action "
        "items of target_chats (or file_name) into exports/<brief_title>.md and returns its path.\n"
        "Side effects: 'project_brief' writes or overwrites an export file; 'knowledge_index' rewrites the "
        "cached index file. Chat files are never modified."
    ),
)
def compile_project_insights(
    insight_type: Annotated[
        Literal["action_items", "knowledge_index", "compare_chats", "project_brief"],
        Field(description="Which insight to produce (see the tool description)."),
    ],
    target_chats: Annotated[
        list[str] | None,
        Field(description="Chat file names: all of them for 'project_brief', the first two for 'compare_chats', the first for 'action_items'."),
    ] = None,
    file_name: Annotated[
        str | None,
        Field(description="Single chat file for 'action_items' (or a one-chat 'project_brief'), such as 'my-chat.json'."),
    ] = None,
    file_name_a: Annotated[str | None, Field(description="First chat file for 'compare_chats'.")] = None,
    file_name_b: Annotated[str | None, Field(description="Second chat file for 'compare_chats'.")] = None,
    brief_title: Annotated[
        str, Field(description="Heading and export file name for 'project_brief' (an existing brief with this title is overwritten).")
    ] = "Project Brief",
    rebuild: Annotated[
        bool, Field(description="For 'knowledge_index': rescan all chats instead of returning the cached index.")
    ] = False,
    summary_only: Annotated[
        bool, Field(description="For 'knowledge_index': return file counts per topic instead of full file lists.")
    ] = False,
    client: Client = "default",
) -> str | list[str] | dict:
    return _checked(cc.compile_project_insights(
        insight_type=insight_type,
        target_chats=target_chats,
        file_name=file_name,
        file_name_a=file_name_a,
        file_name_b=file_name_b,
        brief_title=brief_title,
        rebuild=rebuild,
        summary_only=summary_only,
        client=client,
    ))


@mcp.tool(
    title="Maintain Storage",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
    description=(
        "Housekeeping for the archive: compress old chats, find or remove duplicates, change settings, or "
        "report server capabilities. Use it for storage and configuration only, not for reading or "
        "searching chats.\n"
        "op_type 'compress': gzips chats older than days_old (default from settings, 30) in place and "
        "returns {compressed, skipped_recent, days_threshold}; compressed chats stay readable and searchable. "
        "'deduplicate': finds chats with identical content; with dry_run=true (default) it only lists them, "
        "with dry_run=false it permanently deletes the duplicates, returning {dry_run, duplicates, "
        "unique_count}. 'configure': updates settings (see 'settings') and returns which keys changed. "
        "'capabilities': read-only summary of tools, prompts, version and client paths.\n"
        "Destructive only for deduplicate with dry_run=false; ask the user before doing that."
    ),
)
def maintain_storage(
    op_type: Annotated[
        Literal["compress", "deduplicate", "configure", "capabilities"],
        Field(description="Maintenance operation (see the tool description)."),
    ],
    settings: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "For 'configure' only. Allowed keys: auto_save_message_threshold (int, messages before "
                "manage_session_state save persists), compression_days_threshold (int), "
                "summary_pruning_days_threshold (int), client_paths (object: client name to a relative folder), "
                "transcripts_dirs (object: client name to a folder), cursor_transcripts_dir (string). "
                "Unknown keys are ignored."
            )
        ),
    ] = None,
    days_old: Annotated[
        int | None, Field(ge=1, description="For 'compress': minimum age in days; omit to use compression_days_threshold (30 by default).")
    ] = None,
    dry_run: Annotated[
        bool, Field(description="For 'deduplicate': true lists duplicates only; false deletes them permanently.")
    ] = True,
    client: Client = "default",
) -> dict | str:
    return _checked(cc.maintain_storage(
        op_type=op_type,
        settings=settings,
        days_old=days_old,
        dry_run=dry_run,
        client=client,
    ))


@mcp.tool(
    title="Manage Session State",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False),
    description=(
        "Save, auto-save, merge, export or delete archived conversations, and watch the archive for changes. "
        "Use it to persist the current conversation; to import outside history use sync_workspace_data.\n"
        "action 'register_auto_save': remember conversation_name and messages so they are written when the "
        "client disconnects (call it early and re-call it to refresh). 'trigger_auto_save': write the "
        "registered session now. 'save': write messages to <conversation_name>.json, overwriting a chat with "
        "that name; below the auto_save_message_threshold (default 20) it is skipped unless force_save=true. "
        "'merge': append new_messages to file_name, skipping duplicates. 'export_markdown': write "
        "exports/<name>.md. 'delete': permanently delete file_name; refused unless confirm=true, so ask the "
        "user first. 'watch_folder': report {new_files, modified_files, total_tracked} since the last call "
        "(only updates the watch checkpoint).\n"
        "Returns a confirmation string, or the report object for 'watch_folder'."
    ),
)
def manage_session_state(
    action: Annotated[
        Literal["save", "register_auto_save", "trigger_auto_save", "watch_folder", "merge", "export_markdown", "delete"],
        Field(description="Operation to perform (see the tool description)."),
    ],
    conversation_name: Annotated[
        str | None,
        Field(description="Conversation title for 'save' and 'register_auto_save' (also the file name); used as file_name for other actions when file_name is omitted."),
    ] = None,
    messages: MessageList = None,
    force_save: Annotated[
        bool, Field(description="For 'save': write even when the message count is below the auto-save threshold.")
    ] = False,
    file_name: Annotated[
        str | None,
        Field(description="Existing chat file for 'merge', 'export_markdown' and 'delete', such as 'my-chat.json'."),
    ] = None,
    confirm: Annotated[
        bool, Field(description="Must be true for 'delete' to proceed; deletion is permanent.")
    ] = False,
    new_messages: Annotated[
        list[dict[str, Any]] | None,
        Field(description="Messages to append for 'merge' (same shape as 'messages'); falls back to 'messages'."),
    ] = None,
    client: Client = "default",
) -> dict | str:
    return _checked(cc.manage_session_state(
        action=action,
        conversation_name=conversation_name,
        messages=messages,
        force_save=force_save,
        file_name=file_name,
        confirm=confirm,
        new_messages=new_messages,
        client=client,
    ))


# ── Handoff tools ───────────────────────────────────────────────────────────


@mcp.tool(
    title="Save Handoff Receipt",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
    description=(
        "Record what this agent run did and what the next agent must do, as a handoff receipt for the current "
        "workspace. Use it before stopping or handing work to another agent or model; read the current state "
        "with get_handoff_status.\n"
        "A receipt with status 'open' (the default) marks the workspace as blocked until a later receipt "
        "supersedes it with status 'closed' and a closure (closed_by, closed_at, closure_basis). It becomes "
        "stale automatically when any file listed in invalidation.stale_if changes after it was saved. "
        "Receipts are stored as new JSON files in the archive (never overwritten), indexed, and ranked first "
        "in search_history. Returns the saved file name and its receipt_id (pass that as 'supersedes' later)."
    ),
)
def save_handoff_receipt(
    obligations: Annotated[
        dict[str, Any],
        Field(description="What was promised: {'promise': str (the goal), 'scope': [str] (areas or files in scope)}."),
    ],
    work_state: Annotated[
        dict[str, Any],
        Field(
            description=(
                "What was done: {'touched_surfaces': [{'file_path': str, 'summary': str, 'why': str}], "
                "'dependencies': [str]}."
            )
        ),
    ],
    evidence: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Proof: {'checks_run': [{'command': str, 'exit_code': int, 'stdout_summary': str}], "
                "'missing_evidence': [str] (checks skipped or not yet run)}."
            )
        ),
    ],
    invalidation: Annotated[
        dict[str, Any],
        Field(
            description=(
                "When to distrust this receipt and what to do next: {'stale_if': [{'file_path': str} or "
                "{'glob_pattern': str}], 'next_safe_action': str (a direct instruction for the next agent)}."
            )
        ),
    ],
    status: Annotated[
        str,
        Field(description="'open' (work outstanding, blocks the workspace) or 'closed' (finished; needs 'closure')."),
    ] = "open",
    supersedes: Annotated[
        str | None,
        Field(description="receipt_id of the earlier receipt this one replaces, forming a chain."),
    ] = None,
    closure: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "Required to close: {'closed_by': str, 'closed_at': ISO-8601 str, 'closure_basis': str, "
                "'closure_evidence': str}."
            )
        ),
    ] = None,
    receipt_id: Annotated[
        str | None,
        Field(description="Explicit receipt id. Defaults to '<workspace-hash>_<unix-time>'."),
    ] = None,
    client: Client = "default",
) -> str:
    return _checked(cc.save_handoff_receipt(
        obligations=obligations,
        work_state=work_state,
        evidence=evidence,
        invalidation=invalidation,
        status=status,
        supersedes=supersedes,
        closure=closure,
        receipt_id=receipt_id,
        client=client,
    ))


class HandoffStatus(TypedDict, total=False):
    blocked: bool
    blocked_by_receipt: str | None
    active_chain: list[str]
    newest_receipt_id: str | None
    next_safe_action: str | None
    reason: str | None


@mcp.tool(
    title="Get Handoff Status",
    annotations=READ_ONLY,
    description=(
        "Check whether this workspace has unfinished work handed off by an earlier agent. Call it at the start "
        "of a session on a project, before editing; to record a handoff use save_handoff_receipt.\n"
        "Returns {blocked, blocked_by_receipt, active_chain (newest first), newest_receipt_id, "
        "next_safe_action}; with no receipts it returns {blocked: false, reason, active_chain: []}. When "
        "blocked is true, follow next_safe_action (stale receipts tell you to re-verify first). Read-only."
    ),
)
def get_handoff_status(client: Client = "default") -> HandoffStatus:
    return _checked(cc.get_workspace_handoff_state(client=client))


# ── Prompts ─────────────────────────────────────────────────────────────────


@mcp.prompt(title="Start a Chronicle Session")
def start_session() -> str:
    """Get system instructions for auto-saving conversations in the local Chronicle archive."""
    return (
        "You are integrated with Chronicle, a local MCP server that manages, cleans, and indexes chat transcripts. "
        "At the beginning of this chat session, you must call the 'manage_session_state' tool with action='register_auto_save' "
        "to register this conversation. Provide a descriptive title based on the user's initial prompt. "
        "As the conversation progresses, periodically update the registration payload to keep it current. "
        "All saving, merging, and markdown exports are handled automatically behind the scenes."
    )


@mcp.prompt(title="Recall Past Work")
def recall_past_work(
    topic: Annotated[str, Field(description="What to look for, such as a feature, bug, file or decision.")],
) -> str:
    """Search the archive for past conversations about a topic and summarize what was decided."""
    return (
        f"Use Chronicle to recall earlier work on: {topic}\n"
        "1. Call get_handoff_status to see whether unfinished work is pending.\n"
        f"2. Call search_history with query={json.dumps(topic)} (method 'semantic', top_k 5).\n"
        "3. For the best hits, call get_chat_logs with view_type='summary', then view_type='content' with a "
        "small start_msg/end_msg range around the relevant part.\n"
        "4. Summarize the decisions, open questions and next steps, citing the chat file names."
    )


# ── Resources ───────────────────────────────────────────────────────────────


@mcp.resource(
    "chronicle://capabilities",
    name="capabilities",
    title="Chronicle Capabilities",
    description="Server name, version, tools, prompts and configured client paths, as JSON.",
    mime_type="application/json",
)
def capabilities_resource() -> str:
    return json.dumps(cc.get_server_capabilities(), indent=2)


@mcp.resource(
    "chronicle://chats",
    name="chats",
    title="Archived Chats",
    description="First page of chats in the default archive namespace (same as get_chat_logs with no chat_id).",
    mime_type="text/plain",
)
def chats_resource() -> str:
    return "\n".join(cc.list_all_stored_chats(page=1, per_page=50))


# ── Entry point ─────────────────────────────────────────────────────────────


def run() -> None:
    """Run the stdio server, flushing any registered auto-save session on exit."""
    import atexit

    def flush_on_exit() -> None:
        try:
            cc.trigger_auto_save_on_session_end()
        except Exception:
            pass

    atexit.register(flush_on_exit)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
