from mcp.server.fastmcp import FastMCP

from chat_core import get_connector

mcp = FastMCP("Universal Chat Connector")
cc = get_connector()

# ── Core tools ──────────────────────────────────────────────────────────────


@mcp.tool()
def list_all_stored_chats(
    page: int = 1, per_page: int = 50, client: str = "default"
) -> list[str]:
    """List all available archive files in the index with pagination to save tokens."""
    return cc.list_all_stored_chats(page, per_page, client)


@mcp.tool()
def search_chats_by_keywords(
    keywords: list[str], limit: int = 50, client: str = "default"
) -> list[str]:
    """Search conversation archives using thematic keywords (truncated to limit to save tokens)."""
    return cc.search_chats_by_keywords(keywords, limit, client)


@mcp.tool()
def read_chat_message_range(
    file_name: str,
    start_msg: int = 1,
    end_msg: int = 20,
    max_msg_len: int = 1000,
    summarize_code: bool = True,
    client: str = "default",
) -> str:
    """Read specific messages (summarize_code=True & max_msg_len=1000 active by default to save tokens)."""
    return cc.read_chat_message_range(
        file_name, start_msg, end_msg, max_msg_len, summarize_code, client
    )


@mcp.tool()
def save_current_conversation_state(
    conversation_name: str,
    messages: list[dict],
    force_save: bool = False,
    client: str = "default",
) -> str:
    """Save ongoing session history to storage."""
    return cc.save_current_conversation_state(conversation_name, messages, force_save, client)


# ── High impact ─────────────────────────────────────────────────────────────


@mcp.tool()
def delete_stored_chat(file_name: str, confirm: bool = False, client: str = "default") -> str:
    """Remove a stored chat archive (requires confirm=true)."""
    return cc.delete_stored_chat(file_name, confirm, client)


@mcp.tool()
def get_chat_metadata(file_name: str, client: str = "default") -> dict:
    """Return title, message count, file size, and last modified date."""
    return cc.get_chat_metadata(file_name, client)


@mcp.tool()
def merge_conversation_into_archive(
    file_name: str, new_messages: list[dict], client: str = "default"
) -> str:
    """Append new messages to an existing chat archive."""
    return cc.merge_conversation_into_archive(file_name, new_messages, client)


@mcp.tool()
def export_chat_as_markdown(
    file_name: str, output_name: str | None = None, client: str = "default"
) -> str:
    """Export a chat archive as a human-readable markdown file."""
    return cc.export_chat_as_markdown(file_name, output_name, client)


# ── Search and retrieval ────────────────────────────────────────────────────


@mcp.tool()
def search_chats_semantic(query: str, top_k: int = 10, client: str = "default") -> list[dict]:
    """Search archives using TF-IDF semantic similarity (no API key required)."""
    return cc.search_chats_semantic(query, top_k, client)


@mcp.tool()
def get_chat_summary(file_name: str, client: str = "default") -> str:
    """Generate a one-paragraph extractive summary of a chat."""
    return cc.get_chat_summary(file_name, client)


@mcp.tool()
def find_related_chats(file_name: str, top_k: int = 5, client: str = "default") -> list[dict]:
    """Find chats semantically similar to a given archive."""
    return cc.find_related_chats(file_name, top_k, client)


@mcp.tool()
def filter_chats_by_date_range(
    start_date: str, end_date: str, limit: int = 50, client: str = "default"
) -> list[dict]:
    """Filter chats modified between two dates (YYYY-MM-DD)."""
    return cc.filter_chats_by_date_range(start_date, end_date, limit, client)


# ── Automation and workflows ────────────────────────────────────────────────


@mcp.tool()
def register_session_for_auto_save(
    conversation_name: str, messages: list[dict], client: str = "default"
) -> str:
    """Register the current session for auto-save on session end."""
    return cc.register_session_for_auto_save(conversation_name, messages, client)


@mcp.tool()
def trigger_auto_save_on_session_end() -> str:
    """Flush any pending registered session to disk."""
    return cc.trigger_auto_save_on_session_end()


@mcp.tool()
def watch_chats_folder(client: str = "default") -> dict:
    """Report new, modified, or deleted chat files since last watch."""
    return cc.watch_chats_folder(client)


@mcp.tool()
def import_chat_from_content(title: str, content: str, client: str = "default") -> str:
    """Import a chat from a JSON string (clipboard paste or API response)."""
    return cc.import_chat_from_content(title, content, client)


@mcp.tool()
def import_chat_from_local_path(
    source_path: str, title: str | None = None, client: str = "default"
) -> str:
    """Import a chat from a local JSON file path."""
    return cc.import_chat_from_local_path(source_path, title, client)


@mcp.tool()
def sync_cursor_agent_transcripts(limit: int = 50) -> dict:
    """Import Cursor agent transcript JSONL files into the cursor client folder."""
    return cc.sync_cursor_agent_transcripts(limit)


# ── Intelligence layer ──────────────────────────────────────────────────────


@mcp.tool()
def extract_action_items(file_name: str, client: str = "default") -> list[str]:
    """Extract TODOs and action items from a stored conversation."""
    return cc.extract_action_items(file_name, client)


@mcp.tool()
def build_knowledge_index(
    rebuild: bool = False, summary_only: bool = False, client: str = "default"
) -> dict:
    """Build or return a topic-tagged index of stored chats (use summary_only=True to save tokens)."""
    return cc.build_knowledge_index(rebuild, summary_only, client)


@mcp.tool()
def compare_two_chats(file_name_a: str, file_name_b: str, client: str = "default") -> str:
    """Compare two chats by shared and unique keyword topics."""
    return cc.compare_two_chats(file_name_a, file_name_b, client)


@mcp.tool()
def generate_project_brief_from_chats(
    file_names: list[str], brief_title: str = "Project Brief", client: str = "default"
) -> str:
    """Combine multiple chats into a single project brief markdown file."""
    return cc.generate_project_brief_from_chats(file_names, brief_title, client)


# ── Config and ops ──────────────────────────────────────────────────────────


@mcp.tool()
def configure_connector_settings(settings: dict) -> str:
    """Update connector config (thresholds, client paths, compression, transcripts dir)."""
    return cc.configure_connector_settings(settings)


@mcp.tool()
def compress_old_chat_archives(days_old: int | None = None, client: str = "default") -> dict:
    """Gzip chat archives older than N days to save disk space."""
    return cc.compress_old_chat_archives(days_old, client)


@mcp.tool()
def deduplicate_stored_chats(dry_run: bool = True, client: str = "default") -> dict:
    """Find (and optionally remove) duplicate chat archives by content hash."""
    return cc.deduplicate_stored_chats(dry_run, client)


@mcp.tool()
def get_server_capabilities() -> dict:
    """List all available tools, transports, and feature categories."""
    return cc.get_server_capabilities()


if __name__ == "__main__":
    mcp.run(transport="stdio")
