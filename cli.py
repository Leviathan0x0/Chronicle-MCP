import os
import sys
import json
import shutil
import argparse
from pathlib import Path

SETTINGS_FILE_PATH = Path.home() / ".chronicle_settings.json"

# Load saved chats folder settings and set CHRONICLE_BASE_DIR before other imports
if SETTINGS_FILE_PATH.exists():
    try:
        with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as f:
            _settings = json.load(f)
        if "chats_folder" in _settings:
            os.environ["CHRONICLE_BASE_DIR"] = _settings["chats_folder"]
    except Exception:
        pass

def get_config_path(app_name):
    """Calculates the exact, absolute configuration file path based on the operating system."""
    home = Path.home()
    system = sys.platform
    app = app_name.lower().replace(" ", "").replace("-", "")

    # 1. Cursor Setup
    if app in ["cursor", "cursoragent"]:
        return home / ".cursor" / "mcp.json"

    # 2. Claude Code Setup
    if app == "claude" or app == "claudecode":
        return home / ".claude.json"

    # 3. Visual Studio Code / RooCode / Cline
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

    # 5. Windsurf Setup
    if app == "windsurf":
        if system == "darwin":
            return home / "Library/Application Support/Windsurf/mcp.json"
        elif system == "win32":
            appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
            return appdata / "Windsurf" / "mcp.json"
        else:
            return home / ".config" / "Windsurf" / "mcp.json"

    # 6. Claude Desktop Setup
    if app == "claudedesktop":
        if system == "darwin":
            return home / "Library/Application Support/Claude/claude_desktop_config.json"
        elif system == "win32":
            appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
            return appdata / "Claude" / "claude_desktop_config.json"
        else:
            return home / ".config" / "Claude" / "claude_desktop_config.json"

    # 7. ChatGPT Desktop Setup
    if app == "chatgptdesktop":
        if system == "darwin":
            return home / "Library/Application Support/ChatGPT/mcp.json"
        elif system == "win32":
            appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
            return appdata / "ChatGPT" / "mcp.json"
        else:
            return home / ".config" / "ChatGPT" / "mcp.json"

    # 8. Antigravity Setup
    if app == "antigravity":
        return home / ".antigravity" / "mcp.json"
    if app == "antigravityide":
        return home / ".antigravity-ide" / "mcp.json"
    if app == "antigravity2.0" or app == "antigravity20":
        return home / ".antigravity-2.0" / "mcp.json"
    if app == "antigravitycli":
        return home / ".antigravity-cli" / "mcp.json"

    # Generic Fallback Scheme for Emerging Vibe Coding Tools
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

def getch():
    import sys
    import tty
    import termios
    import select
    import os
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch_bytes = os.read(fd, 1)
        if not ch_bytes:
            return ""
        ch = ch_bytes.decode("utf-8", errors="ignore")
        if ch == "\x1b":
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                extra_bytes = os.read(fd, 2)
                ch += extra_bytes.decode("utf-8", errors="ignore")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def select_apps_interactive():
    import sys
    
    options = [
        {"id": "cursor", "title": "Cursor", "checked": False},
        {"id": "vscode", "title": "VS Code (Cline / Roo Code)", "checked": False},
        {"id": "trae", "title": "Trae IDE", "checked": False},
        {"id": "claude", "title": "Claude Code", "checked": False},
        {"id": "windsurf", "title": "Windsurf", "checked": False},
        {"id": "claude-desktop", "title": "Claude Desktop", "checked": False},
        {"id": "chatgpt-desktop", "title": "ChatGPT Desktop", "checked": False},
        {"id": "antigravity", "title": "Antigravity", "checked": False},
        {"id": "other", "title": "Other (Custom Entry)", "checked": False}
    ]
    
    sub_options = [
        {"id": "antigravity-ide", "title": "Antigravity IDE", "checked": False, "indent": True},
        {"id": "antigravity-2.0", "title": "Antigravity 2.0", "checked": False, "indent": True},
        {"id": "antigravity-cli", "title": "Antigravity CLI", "checked": False, "indent": True}
    ]
    
    def get_visible_items():
        visible = []
        for opt in options:
            visible.append(opt)
            if opt["id"] == "antigravity" and opt["checked"]:
                for sub in sub_options:
                    visible.append(sub)
        return visible

    cursor_idx = 0
    lines_count = 0
    
    print("\n\033[1;35mPlease select the applications/IDEs where you want to install Chronicle MCP:\033[0m")
    print("\033[90m  (Use arrow keys to navigate, Space to toggle, Enter to confirm)\033[0m")
    
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    
    try:
        while True:
            visible_items = get_visible_items()
            if cursor_idx >= len(visible_items):
                cursor_idx = len(visible_items) - 1
            if cursor_idx < 0:
                cursor_idx = 0
                
            if lines_count > 0:
                sys.stdout.write("\033[F" * lines_count + "\033[J")
                
            lines = []
            for idx, item in enumerate(visible_items):
                is_focused = (idx == cursor_idx)
                
                if item["checked"]:
                    checked_str = "\033[1;32m[✓]\033[0m"
                else:
                    checked_str = "\033[90m[ ]\033[0m"
                    
                indent = "    " if item.get("indent") else "  "
                pointer = "\033[1;36m>\033[0m " if is_focused else "  "
                
                if is_focused:
                    text = f"\033[1;37m{item['title']}\033[0m"
                else:
                    text = f"\033[37m{item['title']}\033[0m"
                    
                lines.append(f"{pointer}{indent}{checked_str} {text}")
                
            sys.stdout.write("\n".join(lines) + "\n")
            sys.stdout.flush()
            lines_count = len(lines)
            
            key = getch()
            if key == '\x1b[A':  # Up
                cursor_idx = (cursor_idx - 1) % len(visible_items)
            elif key == '\x1b[B':  # Down
                cursor_idx = (cursor_idx + 1) % len(visible_items)
            elif key == ' ':  # Space
                item = visible_items[cursor_idx]
                item["checked"] = not item["checked"]
                
                if item["id"] == "antigravity" and not item["checked"]:
                    for sub in sub_options:
                        sub["checked"] = False
            elif key == '\r' or key == '\n':  # Enter
                break
            elif key == '\x03' or key == '\x1b':  # Ctrl+C or Escape
                raise KeyboardInterrupt
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        
    return visible_items

def run_setup_wizard():
    # Phase 1: The Temporal Split
    print("\033[1;36m── Chronicle Archive Setup ─────────────────────────────────────\033[0m")
    print("Do you want to split a monolithic conversations.json file?")
    export_path_str = input("Enter path to export file (or press ENTER to skip): ").strip()
    
    split_file_path = None
    if not export_path_str:
        print("\033[90m → Skipping monolithic split step.\033[0m")
    else:
        resolved_export = Path(export_path_str).expanduser().resolve()
        if resolved_export.exists() and resolved_export.is_file():
            split_file_path = resolved_export
        else:
            print("\033[33m ⚠ File not found at that path. Skipping split.\033[0m")

    # Phase 2: Define Storage Path
    print()
    chats_folder_input = input("Enter path to folder containing your conversations [Default: ~/universal-chats]: ").strip()
    if not chats_folder_input:
        chats_folder_input = "~/universal-chats"
    
    resolved_storage_path = Path(chats_folder_input).expanduser().resolve()
    
    dir_existed = resolved_storage_path.exists()
    resolved_storage_path.mkdir(parents=True, exist_ok=True)
    if not dir_existed:
        print(f"\033[32m✓ Initialized storage directory: {resolved_storage_path}\033[0m")
    else:
        print(f"\033[32m✓ Using existing storage directory: {resolved_storage_path}\033[0m")
        
    set_chats_folder(resolved_storage_path)
    os.environ["CHRONICLE_BASE_DIR"] = str(resolved_storage_path)

    # Run split if requested and valid
    if split_file_path:
        print(f"Splitting '{split_file_path.name}' into '{resolved_storage_path}'...")
        split_export_file(split_file_path, resolved_storage_path)
        print("\033[32m ✓ Successfully split logs.\033[0m")

    # Phase 3: MCQ
    supported_targets = [
        "cursor", "vscode", "trae", "claude", "windsurf", 
        "claude-desktop", "chatgpt-desktop", "antigravity",
        "antigravity-ide", "antigravity-2.0", "antigravity-cli"
    ]
    
    app_mapping = {
        1: "cursor",
        2: "vscode",
        3: "trae",
        4: "claude",
        5: "windsurf",
        6: "claude-desktop",
        7: "chatgpt-desktop",
        8: "antigravity"
    }

    selected_apps = []
    while True:
        invalid_apps = []
        selected_apps = []
        
        # Check if tty and termios can be imported for interactive mode
        is_interactive = sys.stdin.isatty()
        try:
            import tty
            import termios
            import select
        except ImportError:
            is_interactive = False
            
        if is_interactive:
            try:
                visible_items = select_apps_interactive()
                has_other = False
                for item in visible_items:
                    if item["checked"]:
                        if item["id"] == "other":
                            has_other = True
                        else:
                            selected_apps.append(item["id"])
                
                if has_other:
                    custom_entry = input("Enter the name of your custom application: ").strip()
                    custom_entry_lower = custom_entry.lower()
                    if custom_entry_lower in supported_targets:
                        selected_apps.append(custom_entry_lower)
                    else:
                        invalid_apps.append(custom_entry_lower)
            except KeyboardInterrupt:
                print("\n\033[31mSetup cancelled by user.\033[0m")
                sys.exit(1)
        else:
            # Fallback for non-TTY / tests / Windows automated setups
            print("\nPlease select the applications/IDEs where you want to install Chronicle MCP:")
            print("  [1] Cursor")
            print("  [2] VS Code (Cline / Roo Code)")
            print("  [3] Trae IDE")
            print("  [4] Claude Code")
            print("  [5] Windsurf")
            print("  [6] Claude Desktop")
            print("  [7] ChatGPT Desktop")
            print("  [8] Antigravity")
            print("  [9] Other (Custom Entry)")
            
            choices_input = input("Enter choices as comma-separated numbers (e.g., 1, 3, 5): ").strip()
            if not choices_input:
                print("\033[90m → No choices selected. Skipping MCP installation.\033[0m")
                selected_apps = []
            else:
                parts = [p.strip() for p in choices_input.split(",") if p.strip()]
                has_other = False
                has_antigravity = False
                
                for part in parts:
                    if part.isdigit():
                        num = int(part)
                        if num in app_mapping:
                            if app_mapping[num] == "antigravity":
                                has_antigravity = True
                            else:
                                selected_apps.append(app_mapping[num])
                        elif num == 9:
                            has_other = True
                        else:
                            invalid_apps.append(part)
                    else:
                        invalid_apps.append(part)
                        
                if has_antigravity:
                    selected_apps.append("antigravity")
                    sub_choices = input("Select Antigravity options: [1] Antigravity IDE, [2] Antigravity 2.0, [3] Antigravity CLI (comma-separated): ").strip()
                    if sub_choices:
                        sub_parts = [p.strip() for p in sub_choices.split(",") if p.strip()]
                        sub_mapping = {
                            1: "antigravity-ide",
                            2: "antigravity-2.0",
                            3: "antigravity-cli"
                        }
                        for sp in sub_parts:
                            if sp.isdigit():
                                s_num = int(sp)
                                if s_num in sub_mapping:
                                    selected_apps.append(sub_mapping[s_num])
                                else:
                                    invalid_apps.append(f"antigravity-sub-{sp}")
                            else:
                                invalid_apps.append(sp)
                                
                if has_other:
                    custom_entry = input("Enter the name of your custom application: ").strip()
                    custom_entry_lower = custom_entry.lower()
                    if custom_entry_lower in supported_targets:
                        selected_apps.append(custom_entry_lower)
                    else:
                        invalid_apps.append(custom_entry_lower)
                        
        selected_apps = list(dict.fromkeys(selected_apps))
        
        if invalid_apps:
            for inv in invalid_apps:
                print(f'\033[33m ⚠ App/IDE "{inv}" is not currently supported by auto-install.\033[0m')
            
            if selected_apps:
                valid_apps_str = ", ".join(selected_apps)
                ans = input(f"Would you like to proceed with installing to the valid selected applications ({valid_apps_str})? [Y/n]: ").strip().lower()
                if ans == "" or ans == "y" or ans == "yes":
                    break
                else:
                    print("Let's re-select your applications.")
                    continue
            else:
                print("No valid applications selected. Let's try selecting again.")
                continue
        else:
            break

    # Phase 4: Configure Injection and Finish Dashboard
    app_titles = {
        "cursor": "Cursor",
        "vscode": "VS Code",
        "trae": "Trae IDE",
        "claude": "Claude Code",
        "windsurf": "Windsurf",
        "claude-desktop": "Claude Desktop",
        "chatgpt-desktop": "ChatGPT Desktop",
        "antigravity": "Antigravity",
        "antigravity-ide": "Antigravity IDE",
        "antigravity-2.0": "Antigravity 2.0",
        "antigravity-cli": "Antigravity CLI"
    }

    installed_apps = []
    for app in selected_apps:
        update_json_config(app)
        installed_apps.append(app_titles.get(app, app.title().replace("-", " ")))
        
    print("\n\033[1;36m── Chronicle Environment Live ──────────────────────────────────\033[0m")
    print(f" \033[32m✓\033[0m Storage Folder : {resolved_storage_path}")
    if installed_apps:
        print(f" \033[32m✓\033[0m Auto-Saved Configs for: [{', '.join(installed_apps)}]")
    else:
        print(" \033[33m⚠\033[0m No applications configured for auto-save.")
    print("\n  How to run the server manually:")
    print("  $ uvx --from chronicle-mcp-server chronicle")
    print("\n  recalled in <1ms · 100% local · zero cloud")
    print("\033[1;36m────────────────────────────────────────────────────────────────\033[0m")

def main():
    # Route to the setup wizard if len(sys.argv) == 1 and sys.stdin.isatty(), or if sys.argv[1] == "setup"
    if (len(sys.argv) == 1 and sys.stdin.isatty()) or (len(sys.argv) == 2 and sys.argv[1] == "setup"):
        run_setup_wizard()
        return

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

    # Subcommand: setup
    subparsers.add_parser("setup", help="Run the interactive setup wizard")

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
    elif args.command == "setup":
        run_setup_wizard()
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