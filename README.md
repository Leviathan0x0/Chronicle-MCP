# Chronicle (Universal Chat Connector)

<p align="center">
  <img src="assets/logo.png" alt="Chronicle Logo" width="400"/>
</p>

Chronicle is a tool that links your AI assistants (like ChatGPT or Claude) to your local saved chats. It helps the AI find, search, compare, and copy your past conversations.

Chronicle is on the MCP Marketplace. You can install it with one click there to connect your AI directly.

### NOTE:
Please give this repository a star if you used it so I can claim the special offers that are given to open-source contributers.

---

## What Chronicle Does

- **Client Folders**: Keeps your saved chats organized in folders for different AIs like ChatGPT or Claude.
- **Special Search**: Helps the AI find past chats by searching for similar meanings and not just exact matching words. You can also search for files saved between certain dates or group files by topic.
- **Token Efficiency**: Hides large chunks of code or shortens very long messages when reading past chats. This helps save data limits and keeps the AI fast.
- **Smart Helpers**: Helps the AI find tasks, summarize conversations, and compare chats.
- **Auto Saving**: Saves your active chats automatically when they get long.
- **Clean Storage**: Finds and deletes duplicate files and shrinks old files to save disk space.

---

## How to Install and Set Up

### Prerequisites
You need Python version 3.10 or higher on your computer.

### Step 1: Download the Files
Clone the folder from GitHub and go inside it:

```bash
git clone https://github.com/Leviathan0x0/Chronicle-MCP.git
cd Chronicle-MCP
```

### Step 2: Set Up Python
Create a private Python setup folder and activate it:

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Required Packages
Install the helper software packages:

```bash
pip install -r requirements.txt
```

---

## How to Import Your Past Saved Chats

You can save new chats automatically or load your old ones.

### 1. Auto Saving
When you chat with an AI that has Chronicle connected, the AI will automatically save your chat in the background to your computer.

### 2. Copying Your Old Chats
If you want to load chats from before you had Chronicle:

#### Step A: Download your data
Go to settings inside ChatGPT or Claude. Click the export data button. You will get a zip file. Unzip this file on your computer.

#### Step B: Split big files
If your downloaded data is one big file with all your chats inside (like ChatGPT's conversations.json file):

```bash
# Activate your python setup folder
source venv/bin/activate

# Run the separator tool to split the big file into separate files
python3 split_chats.py

# Or run it with a custom folder path where you want the chats to go
python3 split_chats.py /path/to/your/folder
```

#### Step C: Move the files
If you have separate files for each chat:
- Copy and paste those files directly into the chats folder on your computer (located at ~/.chronicle/chats/).
- Or use the import tools from the AI to import the files.

---

## Supported File Styles

Chronicle reads and translates different chat styles automatically:

### ChatGPT Style
- **How it works**: ChatGPT saves chats in connected text maps. Chronicle flattens these maps, sorts them by time, and extracts the text.

### Claude Style
- **How it works**: Claude saves chats in list style under chat_messages. Chronicle reads these lists and maps the sender names to user and assistant.

### Generic Style (Cline, Continue, and others)
- **How it works**: Other tools save chats as simple lists. Chronicle reads these lists and matches common words for sender and message content.

---

## Tool List

Chronicle has 25 tools to help your AI manage chats:

### Core Tools
- `list_all_stored_chats`: List your saved files page by page.
- `search_chats_by_keywords`: Search chats using keywords.
- `read_chat_message_range`: Read a range of messages with options to show shortened code to save space.
- `save_current_conversation_state`: Save active chats.

### Edit Tools
- `delete_stored_chat`: Delete a saved chat file.
- `get_chat_metadata`: See file details like size and date.
- `merge_conversation_into_archive`: Add new messages to an old file.
- `export_chat_as_markdown`: Export a chat as a text document.

### Search Tools
- `search_chats_semantic`: Search files using similar meanings.
- `get_chat_summary`: Get a short summary of a chat.
- `find_related_chats`: Find chats that talk about similar things.
- `filter_chats_by_date_range`: Find chats saved between two dates.

### Sync Tools
- `register_session_for_auto_save`: Mark a chat to save later.
- `trigger_auto_save_on_session_end`: Save marked chats now.
- `watch_chats_folder`: Watch your folders for new or changed files.
- `import_chat_from_content`: Import a chat from text.
- `import_chat_from_local_path`: Import a chat from a local file.
- `sync_agent_transcripts`: Sync saved chats from tools like Cursor, Continue, or Cline.
- `sync_cursor_agent_transcripts`: Sync saved chats from Cursor (older version).

### Info Tools
- `extract_action_items`: Find tasks and to-do lists in your chats.
- `build_knowledge_index`: Group your files by topic.
- `compare_two_chats`: See what two chats have in common and what is unique.
- `generate_project_brief_from_chats`: Combine chats into a project summary document.

### System Tools
- `configure_connector_settings`: Change settings like file size limits.
- `compress_old_chat_archives`: Compress old files to save space.
- `deduplicate_stored_chats`: Find and delete duplicate files.
- `get_server_capabilities`: See the list of all tools.

---

## Connecting to Your AI

### Claude Code

If you downloaded the code manually, run this command in your terminal. Note: You must change `/absolute/path/to/` to the actual folder path where you saved the files on your computer.

```bash
claude mcp add-json chronicle '{"command": "python3", "args": ["/absolute/path/to/Chronicle-MCP/chat_server.py"]}'
```

If you installed the tool via the marketplace or npm, you do not need to use a folder path. Run this command instead:

```bash
claude mcp add-json chronicle '{"command": "npx", "args": ["-y", "chronicle-mcp"]}'
```

### Cursor or VS Code

If you downloaded the code manually, go to Cursor settings, find the MCP section, and add a command tool:
- Name: Chronicle
- Command: `python3 /absolute/path/to/Chronicle-MCP/chat_server.py`

If you installed the tool via the marketplace or npm, add this command instead:
- Name: Chronicle
- Command: `npx -y chronicle-mcp`

---

## Testing Your Setup

You can run the test tool to make sure everything works:

```bash
python3 test_all_tools.py
```

---

## License

This project uses the MIT License. See the LICENSE file for details.

<!-- mcp-name: io.github.Leviathan0x0/chronicle-mcp -->
