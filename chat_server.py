from mcp.server.fastmcp import FastMCP
from mcp.types import Icon

from chat_core import get_connector

mcp = FastMCP(
    "Universal Chat Connector",
    website_url="https://github.com/Leviathan0x0/Chronicle-MCP",
    icons=[
        Icon(
            src="https://raw.githubusercontent.com/Leviathan0x0/Chronicle-MCP/main/assets/logo.png",
            mimeType="image/png"
        )
    ]
)
cc = get_connector()

# ── Core tools ──────────────────────────────────────────────────────────────


@mcp.tool()
def search_history(
    query: str = "",
    method: str = "semantic",
    keywords: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
    top_k: int = 10,
    client: str = "default",
    file_name: str | None = None,
) -> list[str] | list[dict]:
    """Search and filter historical transcripts. Options for method: 'semantic', 'keyword', 'date_range', 'related'."""
    return cc.search_history(
        query=query,
        method=method,
        keywords=keywords,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        top_k=top_k,
        client=client,
        file_name=file_name
    )


@mcp.tool()
def get_chat_logs(
    chat_id: str | None = None,
    view_type: str = "content",
    start_msg: int = 1,
    end_msg: int = 20,
    max_msg_len: int = 1000,
    summarize_code: bool = True,
    page: int = 1,
    per_page: int = 50,
    client: str = "default",
) -> str | list[str] | dict:
    """Retrieve lists of files, metadata, summaries, or specific message ranges. Options for view_type: 'content', 'metadata', 'summary'."""
    return cc.get_chat_logs(
        chat_id=chat_id,
        view_type=view_type,
        start_msg=start_msg,
        end_msg=end_msg,
        max_msg_len=max_msg_len,
        summarize_code=summarize_code,
        page=page,
        per_page=per_page,
        client=client
    )


@mcp.tool()
def sync_workspace_data(
    source_type: str,
    payload: str | dict | list | None = None,
    title: str | None = None,
    source_dir: str | None = None,
    limit: int = 50,
    client: str = "default",
) -> dict | str:
    """Ingest and normalize external conversations or live transcripts. Options for source_type: 'agent_transcripts', 'cursor_agent_transcripts', 'local_path', 'raw_content'."""
    return cc.sync_workspace_data(
        source_type=source_type,
        payload=payload,
        title=title,
        source_dir=source_dir,
        limit=limit,
        client=client
    )


@mcp.tool()
def compile_project_insights(
    insight_type: str,
    target_chats: list[str] | None = None,
    file_name: str | None = None,
    file_name_a: str | None = None,
    file_name_b: str | None = None,
    brief_title: str = "Project Brief",
    rebuild: bool = False,
    summary_only: bool = False,
    client: str = "default",
) -> str | list[str] | dict:
    """Analyze historical logs to extract tasks, briefs, or indices. Options for insight_type: 'action_items', 'knowledge_index', 'compare_chats', 'project_brief'."""
    return cc.compile_project_insights(
        insight_type=insight_type,
        target_chats=target_chats,
        file_name=file_name,
        file_name_a=file_name_a,
        file_name_b=file_name_b,
        brief_title=brief_title,
        rebuild=rebuild,
        summary_only=summary_only,
        client=client
    )


@mcp.tool()
def maintain_storage(
    op_type: str,
    settings: dict | None = None,
    days_old: int | None = None,
    dry_run: bool = True,
    client: str = "default",
) -> dict | str:
    """Perform storage maintenance, deduplication, configuration, and capabilities retrieval. Options for op_type: 'compress', 'deduplicate', 'configure', 'capabilities'."""
    return cc.maintain_storage(
        op_type=op_type,
        settings=settings,
        days_old=days_old,
        dry_run=dry_run,
        client=client
    )


@mcp.tool()
def manage_session_state(
    action: str,
    conversation_name: str | None = None,
    messages: list[dict] | None = None,
    force_save: bool = False,
    file_name: str | None = None,
    confirm: bool = False,
    new_messages: list[dict] | None = None,
    client: str = "default",
) -> dict | str:
    """Manage session auto-saving, folder watching, merging, exporting, and deletion. Options for action: 'save', 'register_auto_save', 'trigger_auto_save', 'watch_folder', 'merge', 'export_markdown', 'delete'."""
    return cc.manage_session_state(
        action=action,
        conversation_name=conversation_name,
        messages=messages,
        force_save=force_save,
        file_name=file_name,
        confirm=confirm,
        new_messages=new_messages,
        client=client
    )


@mcp.tool()
def save_handoff_receipt(
    touched_files: list[str],
    open_promises: list[str],
    skipped_checks: list[str],
    next_safe_action: str,
    client: str = "default",
) -> str:
    """Save a handoff receipt for the current run, detailing active state, open commitments, skipped checks, and the next safe action."""
    return cc.save_handoff_receipt(
        touched_files=touched_files,
        open_promises=open_promises,
        skipped_checks=skipped_checks,
        next_safe_action=next_safe_action,
        client=client
    )


@mcp.prompt()
def start_session() -> str:
    """Get system instructions for auto-saving conversations in the local Chronicle archive."""
    return (
        "You are integrated with Chronicle, a local MCP server that manages, cleans, and indexes chat transcripts. "
        "At the beginning of this chat session, you must call the 'manage_session_state' tool with action='register_auto_save' "
        "to register this conversation. Provide a descriptive title based on the user's initial prompt. "
        "As the conversation progresses, periodically update the registration payload to keep it current. "
        "All saving, merging, and markdown exports are handled automatically behind the scenes."
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
