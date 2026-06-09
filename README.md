# 📜 Chronicle (Universal Chat Connector MCP)

[![MCP Version](https://img.shields.io/badge/MCP-1.0-blue.svg)](https://modelcontextprotocol.io/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Chronicle** (Universal Chat Connector) is a premium Model Context Protocol (MCP) server designed to act as a unified bridge between your AI development environments (such as Cursor, Claude Code, and ChatGPT) and your persistent local conversation history. It empowers LLM agents to index, search, compare, export, and extract knowledge or action items from your past coding sessions.

---

## ✨ Features

- **📂 Multi-Client Hub**: Segregate, sync, and browse chat histories across directories dedicated to `cursor`, `claude`, `chatgpt`, or custom folders.
- **🔍 Hybrid Search**: Locate relevant discussions immediately using **keyword tag matching** or local **TF-IDF semantic search** (requires no external API keys or network calls).
- **💡 AI-Ready Intelligence Layer**: Extract action items, compile project briefs across multiple files, rebuild topic indexes, and compare differences between conversation branches.
- **⚡ Automated Synchronization**: Watch chat folders for additions, auto-save pending sessions, and import local log files or clipboard JSON contents.
- **🧹 Storage Management**: Automatically find and remove duplicate files, or compress old logs with gzip to save local disk space.

---

## 🛠️ Tool Architecture & Layout

Chronicle registers **25 specialized tools** divided into logical operational layers:

| Layer | Tools | Description |
| :--- | :--- | :--- |
| **📦 Core** | `list_all_stored_chats`, `search_chats_by_keywords`, `read_chat_message_range`, `save_current_conversation_state` | Basic archive operations and reading log segments. |
| **🛡️ High Impact** | `delete_stored_chat`, `get_chat_metadata`, `merge_conversation_into_archive`, `export_chat_as_markdown` | State modification, metadata reading, and Markdown exporting. |
| **🔍 Search & Retrieval** | `search_chats_semantic`, `get_chat_summary`, `find_related_chats`, `filter_chats_by_date_range` | Semantic querying, summarization, and time-based filtering. |
| **⚙️ Automation** | `register_session_for_auto_save`, `trigger_auto_save_on_session_end`, `watch_chats_folder`, `import_chat_from_content`, `import_chat_from_local_path`, `sync_agent_transcripts`, `sync_cursor_agent_transcripts` | Automated sync, directory monitoring, and universal agent transcript imports. |
| **🧠 Intelligence** | `extract_action_items`, `build_knowledge_index`, `compare_two_chats`, `generate_project_brief_from_chats` | High-level synthesis, comparisons, and knowledge base compiling. |
| **🔧 Ops** | `configure_connector_settings`, `compress_old_chat_archives`, `deduplicate_stored_chats`, `get_server_capabilities` | Configuration, compression tasks, and server info. |

---

## 🚀 Installation & Setup

### 1. Prerequisites
Ensure you have Python 3.10+ installed on your system.

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

*(If `requirements.txt` is not present, the core dependencies are `mcp`, `fastmcp`, and standard python libraries).*

---

## ⚙️ Configuration

The server reads configuration settings from `mcp_config.json`. You can modify settings directly in the JSON file or programmatically via the `configure_connector_settings` tool:

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

## 🔌 Integrating with AI Clients

### Google AntiGravity IDE
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

## 🧪 Verification & Development

You can run the full test suite to verify all 25 tools and 28 integration points:

```bash
python3 test_all_tools.py
```

---

## 📄 License

This project is licensed under the MIT License. See `LICENSE` for details.
