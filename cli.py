import os
import sys
import json
import shutil
import argparse
from pathlib import Path

SETTINGS_FILE_PATH = Path.home() / ".chronicle_settings.json"

def get_config_path(app_name):
    """Calculates the exact, absolute configuration file path based on the operating system."""
    home = Path.home()
    system = sys.platform
    app = app_name.lower().replace(" ", "").replace("-", "")

    # 1. Cursor Setup
    if app == "cursor":
        return home / ".cursor" / "mcp.json"

    # 2. Claude Code Setup
    if app == "claude" or app == "claudecode":
        return home / ".claude.json"

    # 3. Visual Studio Code / Core Code / OpenCode Variations (Cline/RooCode/Continue integration)
    if app in ["vscode", "visualstudiocode", "code", "opencode", "codex"]:
        if system == "darwin":
            return home / "Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
        elif system == "win32":
            appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
            return appdata / "Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
        else:
            return home / ".config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"

    # 4. Trae IDE Setup
    if app == "trae":
        if system == "darwin":
            return home / "Library/Application Support/Trae/mcp.json"
        elif system == "win32":
            appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
            return appdata / "Trae/mcp.json"
        else:
            return home / ".config/Trae/mcp.json"

    # 5. Generic Fallback Scheme for Emerging Vibe Coding Tools (Kiro, MiniMax, Qwen Code, Grok Build, Antigravity)
    # Most 2026 automation tools implement either a home dot-directory configuration file or standard AppData layouts.
    if system == "darwin":
        home_dot_path = home / f".{app}" / "mcp.json"
        if home_dot_path.parent.exists():
            return home_dot_path
        return home / f"Library/Application Support/{app_name}" / "mcp.json"
    elif system == "win32":
        appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
        return appdata / app_name / "mcp.json"
    else:
        return home / f".config/{app}" / "mcp.json"

def split_export_file(export_file_path, output_dir_path):
    """Parses a monolithic chat export JSON and splits it into individual neat files."""
    export_path = Path(export_file_path).expanduser().resolve()
    out_dir = Path(output_dir_path).expanduser().resolve()
    
    if not export_path.exists():
        print(f"Error: The export file '{export_path}' does not exist.", file=sys.stderr)
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(export_path, "r", encoding="utf-8") as f:
            conversations = json.load(f)
            
        if isinstance(conversations, dict):
            conversations = conversations.get("conversations", [conversations])
        elif not isinstance(conversations, list):
            conversations = [conversations]

        print(f"Parsing '{export_path.name}'... Found {len(conversations)} distinct conversation threads.")
        
        saved_count = 0
        for idx, chat in enumerate(conversations):
            title = chat.get("title", f"chat_session_{idx}").strip().replace("/", "_").replace(" ", "_")
            title = (title[:40] + "..") if len(title) > 40 else title
            
            output_file = out_dir / f"{title}.json"
            
            with open(output_file, "w", encoding="utf-8") as out_f:
                json.dump(chat, out_f, indent=2)
            saved_count += 1
            
        print(f"Successfully extracted and stored {saved_count} structured chat logs inside: {out_dir}")
        
    except Exception as e:
        print(f"Failed to split file: {e}", file=sys.stderr)

def get_mcp_config():
    """Dynamically locates the absolute path of uvx to prevent path resolution errors across platforms."""
    uvx_path = shutil.which("uvx")
    
    if not uvx_path:
        uvx_path = "uvx"
        
    return {
        "command": str(uvx_path),
        "args": [
            "--from",
            "chronicle-mcp-server",
            "chronicle"
        ]
    }

def update_json_config(app_name):
    """Safely injects the chronicle-mcp configuration into the resolved target application JSON."""
    file_path = get_config_path(app_name)
    
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

        if "mcpServers" not in data:
            data["mcpServers"] = {}

        data["mcpServers"]["chronicle-mcp"] = get_mcp_config()

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        print(f"Successfully configured chronicle-mcp inside {app_name} at: {file_path}")
    except Exception as e:
        print(f"Error updating {app_name} configuration: {e}", file=sys.stderr)

def set_chats_folder(folder_path):
    """Saves the custom chats folder path to a local settings file."""
    resolved_path = Path(folder_path).expanduser().resolve()
    settings = {"chats_folder": str(resolved_path)}
    
    with open(SETTINGS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    print(f"Successfully set chats directory to: {resolved_path}")

def main():
    parser = argparse.ArgumentParser(description="Chronicle MCP Command Line Interface")
    parser.add_argument("--chats-folder", type=str, help="Set the default local storage directory for chat transcripts")
    
    subparsers = parser.add_subparsers(dest="command")

    # Subcommand: add
    add_parser = subparsers.add_parser("add", help="Add chronicle MCP to a specified application environment")
    add_parser.add_argument("app", type=str, help="The target application interface name (e.g. cursor, claude, trae, vscode, kiro)")
    
    # Subcommand: split
    split_parser = subparsers.add_parser("split", help="Split a combined conversation export into separate files")
    split_parser.add_argument("file", type=str, help="Path to the monolithic conversation.json file")
    split_parser.add_argument("--out", type=str, required=True, help="Target folder directory to save split chats")

    args = parser.parse_args()

    if args.chats_folder:
        set_chats_folder(args.chats_folder)
        return

    if args.command == "split":
        split_export_file(args.file, args.out)
        return
    elif args.command == "add":
        update_json_config(args.app)
        return

    import atexit
    import chat_server

    def flush_on_exit():
        try:
            from chat_core import get_connector
            get_connector().trigger_auto_save_on_session_end()
        except Exception:
            pass

    atexit.register(flush_on_exit)
    chat_server.mcp.run()

if __name__ == "__main__":
    main()