# Chronicle (Universal Chat Connector MCP)

[![MCP Version](https://img.shields.io/badge/MCP-1.0-blue.svg)](https://modelcontextprotocol.io/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Chronicle (Universal Chat Connector) is a premium Model Context Protocol (MCP) server designed to act as a unified bridge between your AI development environments (such as Cursor, Claude Code, and ChatGPT) and your persistent local conversation history. It empowers LLM agents to index, search, compare, export, and extract knowledge or action items from your past coding sessions.

---

## Features

- **Multi-Client Hub**: Segregate, sync, and browse chat histories across directories dedicated to `cursor`, `claude`, `chatgpt`, or custom folders.
- **Hybrid Search**: Locate relevant discussions immediately using keyword tag matching or local TF-IDF semantic search (requires no external API keys or network calls).
- **AI-Ready Intelligence Layer**: Extract action items, compile project briefs across multiple files, rebuild topic indexes, and compare differences between conversation branches.
- **Automated Synchronization**: Watch chat folders for additions, auto-save pending sessions, and import local log files or clipboard JSON contents.
- **Storage Management**: Automatically find and remove duplicate files, or compress old logs with gzip to save local disk space.

---

## Installation and Setup

### 1. Prerequisites
Ensure you have Python 3.10 or higher installed on your system.

### 2. Install Dependencies
Clone the repository and install the required packages inside a virtual environment:

```bash
# Clone the repository
git clone https://github.com/Leviathan0x0/Chronicle-MCP.git
cd Chronicle-MCP

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

Note: The core dependencies are `mcp` and `fastmcp` (which automatically installs its required dependencies).

---

## User Workflows and Data Import

Chronicle is built to manage both ongoing conversations and historical archives from multiple AI providers.

### Workflow 1: Automatic Ongoing Session Saving
When using a client that supports the Chronicle MCP (such as ChatGPT, Claude, or AntiGravity):
1. The agent will automatically call `save_current_conversation_state` at the end of a session or when a threshold is met.
2. The session history is written directly to the target client subfolder (e.g. `~/.chronicle/chats/chatgpt/`).

### Workflow 2: Importing Historical Chat Logs
If you want to import your historical conversation logs created before you installed Chronicle, follow these steps:

#### Step 2a: Export your chat history from your AI provider
Go to the settings panel of your AI provider (e.g. ChatGPT, Claude.ai, or your VS Code extensions) and request a data export. This typically downloads a `.zip` archive to your machine. Unzip the file to retrieve the JSON logs.

#### Step 2b: Process unified conversation files (e.g., conversations.json)
If your export is a single unified file containing all conversations (such as ChatGPT's `conversations.json` or Claude's `conversations.json`), run the included utility script to split it:

```bash
# Activate your virtual environment first
source venv/bin/activate

# Split conversations into individual files in the default Chronicle directory (~/.chronicle/chats/)
python3 split_chats.py

# Alternatively, specify a custom directory to output the split chat files
python3 split_chats.py /path/to/custom/chats/dir
```

#### Step 2c: Import individual files
If the export consists of individual conversation JSON files, you can import them in one of three ways:
1. **Copy directly**: Paste the JSON files directly into the target subfolder of your Chronicle root (e.g., `~/.chronicle/chats/claude/` for Claude logs).
2. **Local Path Tool**: Call the `import_chat_from_local_path` tool from your agent, passing the file path.
3. **Pasted Content Tool**: Call the `import_chat_from_content` tool from your agent, passing the JSON string representation of the chat.

---

## Universal Format Normalization

Chronicle is fully equipped to parse and normalize different JSON schemas used by various AI providers:

### ChatGPT Schema (Node Trees)
ChatGPT exports messages using a parent-child mapping structure (`"mapping"` key).
- **Resolution**: Chronicle automatically flattens this node tree, filters out system-level operations, sorts the messages chronologically using `create_time` timestamps, and extracts the text content parts.

### Claude Schema (chat_messages)
Claude exports conversations using a list of messages under a `"chat_messages"` key.
- **Resolution**: Chronicle detects the `"chat_messages"` property, translates `"sender": "human"` to the standard `"User"` prefix, and maps `"sender": "assistant"` to `"Assistant"`.

### Generic and Custom Schemas (Cline, Continue, etc.)
Many local agents (such as Continue or Cline) save conversation logs as flat message arrays under `"messages"`, `"history"`, or directly as top-level JSON arrays.
- **Resolution**: Chronicle parses these files generically. It matches common keys (`role`, `sender`, `text`, `content`) and normalizes aliases (e.g., mapping `Human`/`AI` or `u`/`a` to standard user/assistant representations).

---

## Tool Architecture and Layout

Chronicle registers **25 specialized tools** divided into logical operational layers:

| Layer | Tools | Description |
| :--- | :--- | :--- |
| **Core** | `list_all_stored_chats`, `search_chats_by_keywords`, `read_chat_message_range`, `save_current_conversation_state` | Basic archive operations and reading log segments. |
| **High Impact** | `delete_stored_chat`, `get_chat_metadata`, `merge_conversation_into_archive`, `export_chat_as_markdown` | State modification, metadata reading, and Markdown exporting. |
| **Search & Retrieval** | `search_chats_semantic`, `get_chat_summary`, `find_related_chats`, `filter_chats_by_date_range` | Semantic querying, summarization, and time-based filtering. |
| **Automation** | `register_session_for_auto_save`, `trigger_auto_save_on_session_end`, `watch_chats_folder`, `import_chat_from_content`, `import_chat_from_local_path`, `sync_agent_transcripts`, `sync_cursor_agent_transcripts` | Automated sync, directory monitoring, and universal agent transcript imports. |
| **Intelligence** | `extract_action_items`, `build_knowledge_index`, `compare_two_chats`, `generate_project_brief_from_chats` | High-level synthesis, comparisons, and knowledge base compiling. |
| **Ops** | `configure_connector_settings`, `compress_old_chat_archives`, `deduplicate_stored_chats`, `get_server_capabilities` | Configuration, compression tasks, and server info. |

---

## Configuration

The server reads configuration settings from `mcp_config.json` inside the base directory. You can modify settings directly in the JSON file or programmatically via the `configure_connector_settings` tool:

```json
{
  "auto_save_message_threshold": 20,
  "client_paths": {
    "default": "chats",
    "cursor": "chats/cursor",
    "chatgpt": "chats/chatgpt",
    "claude": "chats/claude"
  },
  "compression_days_threshold": 30,
  "cursor_transcripts_dir": "~/.cursor/projects/.../agent-transcripts",
  "transcripts_dirs": {
    "cursor": "~/.cursor/projects/.../agent-transcripts",
    "continue": "~/.continue/dev_data/history",
    "cline": "~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings",
    "copilot": "~/.copilot-transcripts"
  }
}
```

---

## Integrating with AI Clients

### Google Antigravity IDE
Simply search for the directory or configuration within the **MCP Store** in AntiGravity or register it manually.

### Claude Code
Add the server dynamically using the `claude mcp` CLI command:

```bash
claude mcp add-json chronicle '{"command": "python3", "args": ["/absolute/path/to/Chronicle-MCP/chat_server.py"]}'
```

### Cursor / VS Code
Register the command inside your Cursor MCP settings (`Settings -> Features -> MCP`):

- **Name**: Chronicle
- **Type**: `command`
- **Command**: `python3 /absolute/path/to/Chronicle-MCP/chat_server.py`

---

## Verification and Testing

You can run the full test suite to verify all 25 tools and 28 integration points:

```bash
python3 test_all_tools.py
```

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.
