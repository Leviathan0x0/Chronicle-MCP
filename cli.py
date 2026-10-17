import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

SETTINGS_FILE_PATH = Path.home() / ".chronicle_settings.json"
CUSTOM_APPS_KEY = "custom_apps"
CHATS_FOLDER_KEY = "chats_folder"

SUPPORTED_TARGETS = [
    "cursor",
    "vscode",
    "trae",
    "claude",
    "windsurf",
    "claude-desktop",
    "chatgpt-desktop",
    "antigravity",
    "antigravity-ide",
    "antigravity-2.0",
    "antigravity-cli",
    "kiro",
]

# Load saved chats folder settings and set CHRONICLE_BASE_DIR before other imports
if SETTINGS_FILE_PATH.exists():
    try:
        with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as f:
            _settings = json.load(f)
        if isinstance(_settings, dict) and CHATS_FOLDER_KEY in _settings:
            os.environ["CHRONICLE_BASE_DIR"] = str(_settings[CHATS_FOLDER_KEY])
    except (json.JSONDecodeError, IOError, Exception):
        pass


def load_custom_apps() -> dict:
    """Loads custom app mappings from the settings file."""
    if not SETTINGS_FILE_PATH.exists():
        return {}
    try:
        with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as f:
            settings = json.load(f)
        if isinstance(settings, dict):
            return settings.get(CUSTOM_APPS_KEY, {})
        return {}
    except (json.JSONDecodeError, IOError, Exception):
        return {}


def save_custom_app(name: str, paths: list[Path]):
    """Saves a resolved custom app's config path to the settings file."""
    if not paths:
        return

    settings = {}
    if SETTINGS_FILE_PATH.exists():
        loaded = _load_json_lenient(SETTINGS_FILE_PATH)
        if loaded is None:
            if SETTINGS_FILE_PATH.stat().st_size > 0:
                try:
                    shutil.copy2(SETTINGS_FILE_PATH, SETTINGS_FILE_PATH.with_suffix(".json.bak"))
                except Exception:
                    pass
            settings = {}
        else:
            settings = loaded

    if CUSTOM_APPS_KEY not in settings:
        settings[CUSTOM_APPS_KEY] = {}

    settings[CUSTOM_APPS_KEY][name] = list(set([str(p.resolve()) for p in paths]))

    try:
        dir_name = SETTINGS_FILE_PATH.parent
        dir_name.mkdir(parents=True, exist_ok=True)
        fd, tmp_file = tempfile.mkstemp(dir=str(dir_name), prefix=".tmp_settings_", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, SETTINGS_FILE_PATH)
    except (IOError, OSError) as e:
        print(
            f"Warning: Could not save custom app settings to {SETTINGS_FILE_PATH}: {e}",
            file=sys.stderr,
        )


def set_chats_folder(folder_path):
    """Saves the custom chats folder path to a local settings file."""
    resolved_path = Path(folder_path).expanduser().resolve()

    settings = {}
    if SETTINGS_FILE_PATH.exists():
        loaded = _load_json_lenient(SETTINGS_FILE_PATH)
        if loaded is None:
            if SETTINGS_FILE_PATH.stat().st_size > 0:
                try:
                    shutil.copy2(SETTINGS_FILE_PATH, SETTINGS_FILE_PATH.with_suffix(".json.bak"))
                except Exception:
                    pass
            settings = {}
        else:
            settings = loaded

    settings[CHATS_FOLDER_KEY] = str(resolved_path)

    try:
        dir_name = SETTINGS_FILE_PATH.parent
        dir_name.mkdir(parents=True, exist_ok=True)
        fd, tmp_file = tempfile.mkstemp(dir=str(dir_name), prefix=".tmp_settings_", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, SETTINGS_FILE_PATH)
        print(f"Successfully set chats directory to: {resolved_path}")
    except (IOError, OSError) as e:
        print(
            f"Error: Could not write to settings file at {SETTINGS_FILE_PATH}: {e}",
            file=sys.stderr,
        )


def find_executable_or_app(app_name):
    """Checks if the application's executable or application package exists on the system."""
    home = Path.home()
    system = sys.platform

    # Check if direct name exists on PATH
    if shutil.which(app_name):
        return True

    # Check common suffix/variations on PATH
    for suffix in ["", ".exe", ".cmd", ".bat"]:
        if shutil.which(app_name + suffix):
            return True
        if shutil.which(app_name.lower() + suffix):
            return True

    if system == "darwin":
        # Check standard macOS Applications folder
        app_dirs = [Path("/Applications"), home / "Applications"]
        for app_dir in app_dirs:
            if app_dir.exists():
                for name in [
                    app_name,
                    app_name.title(),
                    app_name.upper(),
                    app_name.lower(),
                ]:
                    if (app_dir / f"{name}.app").exists():
                        return True
    elif system == "win32":
        # Check common Windows program directories
        program_files = [
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
            Path(os.environ.get("LocalAppData", home / "AppData\\Local")),
        ]
        for pf in program_files:
            if pf.exists():
                for name in [app_name, app_name.title(), app_name.lower()]:
                    if (pf / name).exists() or (pf / f"{name}.exe").exists():
                        return True
                    # Check first level children for matching directory name
                    try:
                        for sub in pf.iterdir():
                            if sub.is_dir() and sub.name.lower() == name.lower():
                                return True
                    except OSError:
                        pass
    return False


def _load_json_lenient(path: Path) -> dict | None:
    """Safely loads a JSON or JSONC file, ignoring comments and trailing commas. Returns None on parse/IO failure."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.strip():
            return {}

        # Strip comments
        import re

        pattern = re.compile(r'("(?:[^"\\]|\\.)*")|(/\*.*?\*/)|(//.*)', re.DOTALL)
        content_clean = pattern.sub(lambda m: m.group(1) if m.group(1) else "", content)

        # Strip trailing commas
        content_clean = re.sub(r",\s*([\]}])", r"\1", content_clean)

        parsed = json.loads(content_clean)
        return parsed if isinstance(parsed, dict) else {}
    except (IOError, json.JSONDecodeError) as e:
        print(
            f"Warning: Could not read or parse JSON file at {path}: {e}",
            file=sys.stderr,
        )
        return None


def discover_config_files_by_content(
    app_name: str, search_dirs: list[Path]
) -> list[Path]:
    """Scans directories for JSON files that look like MCP configs by content."""
    found_paths = []
    app_clean = app_name.lower().replace(" ", "").replace("-", "").replace("_", "")

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        try:
            for item in search_dir.iterdir():
                if not item.is_dir():
                    continue
                item_clean = (
                    item.name.lower().replace(" ", "").replace("-", "").replace("_", "")
                )

                if app_clean in item_clean or item_clean in app_clean:
                    # Walk the directory with a depth limit
                    for root, _, files in os.walk(item):
                        root_path = Path(root)
                        # Crude depth check
                        if len(root_path.parts) - len(item.parts) > 3:
                            continue

                        for file in files:
                            if file.endswith(".json") or file.endswith(".jsonc"):
                                file_path = root_path / file
                                try:
                                    data = _load_json_lenient(file_path)
                                    if isinstance(data, dict) and any(
                                        key in data
                                        for key in ["mcpServers", "mcp", "servers"]
                                    ):
                                        found_paths.append(file_path)
                                    # Nested check for VSCode-style globalStorage
                                    elif "globalStorage" in str(
                                        file_path
                                    ) and "settings" in str(file_path):
                                        if isinstance(data, dict) and any(
                                            key in data
                                            for key in ["mcpServers", "mcp", "servers"]
                                        ):
                                            found_paths.append(file_path)
                                except (IOError, OSError, TypeError):
                                    pass  # Ignore files we can't read/parse
        except OSError:  # Permissions error
            pass

    return list(set(found_paths))


def search_config_paths(app_name):
    """Searches standard application data directories for folders matching app_name and returns possible config paths."""
    home = Path.home()
    system = sys.platform
    app_clean = app_name.lower().replace(" ", "").replace("-", "").replace("_", "")
    found_paths = []

    # Define directories to search
    search_dirs = []
    if system == "darwin":
        search_dirs.append(home / "Library/Application Support")
        search_dirs.append(home)  # for dotfolders
    elif system == "win32":
        appdata = os.environ.get("APPDATA")
        localappdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            search_dirs.append(Path(appdata))
        if localappdata:
            search_dirs.append(Path(localappdata))
        search_dirs.append(home)
    else:
        config_home = os.environ.get("XDG_CONFIG_HOME")
        if config_home:
            search_dirs.append(Path(config_home))
        else:
            search_dirs.append(home / ".config")
        search_dirs.append(home)

    mcp_filenames = [
        "mcp.json",
        "mcp_config.json",
        "cline_mcp_settings.json",
        "claude_desktop_config.json",
        "opencode.json",
        "opencode.jsonc",
    ]

    # Fast path: check for hardcoded filenames
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        try:
            for item in search_dir.iterdir():
                if not item.is_dir():
                    continue
                item_clean = (
                    item.name.lower().replace(" ", "").replace("-", "").replace("_", "")
                )

                # Check if this folder matches the app name
                if app_clean in item_clean or item_clean in app_clean:
                    # Check for existing config files
                    for fname in mcp_filenames:
                        cfg_file = item / fname
                        if cfg_file.exists():
                            found_paths.append(cfg_file)

                        # Check data/settings/ (for Cline style)
                        nested_settings = item / "data" / "settings" / fname
                        if nested_settings.exists():
                            found_paths.append(nested_settings)

                        # Check globalStorage/
                        global_settings = item / "globalStorage"
                        if global_settings.exists():
                            try:
                                for sub in global_settings.glob("**/settings/" + fname):
                                    found_paths.append(sub)
                            except OSError:
                                pass

                    # If we found matching directory, also propose creating mcp.json/mcp_config.json inside it
                    found_paths.append(item / "mcp.json")
                    found_paths.append(item / "mcp_config.json")
        except OSError:
            pass

    # Slow path: content-based discovery
    content_paths = discover_config_files_by_content(app_name, search_dirs)
    found_paths.extend(content_paths)

    return list(set(found_paths))


def resolve_custom_entry(entry: str) -> tuple[str, Path | None]:
    """Resolves a custom entry, which can be an app name or a direct path."""
    entry_path = Path(entry).expanduser()
    try:
        if entry_path.exists():
            # It's a path to a file or directory
            if entry_path.is_file():
                return entry_path.stem.lower(), entry_path
            elif entry_path.is_dir():
                return entry_path.name.lower(), entry_path
    except OSError:  # Path might be too long or invalid
        pass

    # It's an app name
    return entry.lower().replace(" ", ""), None


PATH_TEMPLATES = {
    "default": [
        "{HOME}/.{app}/mcp.json",
        "{HOME}/.{app}/mcp_config.json",
        "{XDG_CONFIG_HOME}/{app}/mcp.json",
        "{XDG_CONFIG_HOME}/{app}/mcp_config.json",
    ],
    "darwin": {
        "default": [
            "{APP_SUPPORT}/{app_name}/mcp.json",
            "{APP_SUPPORT}/{app_name}/mcp_config.json",
            "{APP_SUPPORT}/{app}/mcp.json",
            "{APP_SUPPORT}/{app}/mcp_config.json",
        ]
    },
    "win32": {
        "default": [
            "{APPDATA}/{app_name}/mcp.json",
            "{APPDATA}/{app_name}/mcp_config.json",
            "{APPDATA}/{app}/mcp.json",
            "{APPDATA}/{app}/mcp_config.json",
        ]
    },
    "cursor": ["{HOME}/.cursor/mcp.json"],
    "claude": ["{HOME}/.claude.json"],
    "vscode": [
        "{HOME}/.cline/data/settings/cline_mcp_settings.json",
        "{HOME}/.roocode/data/settings/cline_mcp_settings.json",
        "{APP_SUPPORT}/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
        "{APP_SUPPORT}/Code/User/globalStorage/roovet.roo-cline/settings/cline_mcp_settings.json",
    ],
    "trae": [
        "{HOME}/.trae/mcp.json",
        "{APP_SUPPORT}/Trae/mcp.json",
        "{XDG_CONFIG_HOME}/Trae/mcp.json",
    ],
    "windsurf": [
        "{HOME}/.codeium/windsurf/mcp_config.json",
        "{APP_SUPPORT}/Windsurf/mcp.json",
        "{XDG_CONFIG_HOME}/Windsurf/mcp.json",
    ],
    "claudedesktop": [
        "{APP_SUPPORT}/Claude/claude_desktop_config.json",
        "{XDG_CONFIG_HOME}/Claude/claude_desktop_config.json",
    ],
    "chatgptdesktop": [
        "{APP_SUPPORT}/ChatGPT/mcp.json",
        "{XDG_CONFIG_HOME}/ChatGPT/mcp.json",
    ],
    "kiro": [
        "{HOME}/.kiro/settings/mcp.json",
        "{APP_SUPPORT}/Kiro/User/settings/mcp.json",
        "{APP_SUPPORT}/Kiro/mcp.json",
        "{XDG_CONFIG_HOME}/Kiro/User/settings/mcp.json",
        "{XDG_CONFIG_HOME}/Kiro/mcp.json",
    ],
    "opencode": [
        "{XDG_CONFIG_HOME}/opencode/opencode.jsonc",
        "{XDG_CONFIG_HOME}/opencode/opencode.json",
        "{APP_SUPPORT}/ai.opencode.desktop/mcp.json",
        "{APP_SUPPORT}/ai.opencode.desktop/mcp_config.json",
    ],
    "antigravity": [
        "{HOME}/.antigravity/mcp.json",
        "{HOME}/.gemini/antigravity/mcp_config.json",
        "{HOME}/.gemini/antigravity/mcp.json",
        "{HOME}/.gemini/config/mcp_config.json",
        "{APP_SUPPORT}/Antigravity/mcp.json",
        "{APP_SUPPORT}/Antigravity/mcp_config.json",
        "{APP_SUPPORT}/antigravity/mcp.json",
        "{APP_SUPPORT}/antigravity/mcp_config.json",
        "{XDG_CONFIG_HOME}/Antigravity/mcp.json",
        "{XDG_CONFIG_HOME}/Antigravity/mcp_config.json",
        "{XDG_CONFIG_HOME}/antigravity/mcp.json",
        "{XDG_CONFIG_HOME}/antigravity/mcp_config.json",
    ],
    "antigravity-ide": [
        "{HOME}/.antigravity-ide/mcp.json",
        "{HOME}/.gemini/antigravity-ide/mcp_config.json",
        "{HOME}/.gemini/antigravity-ide/mcp.json",
        "{APP_SUPPORT}/Antigravity IDE/mcp.json",
        "{APP_SUPPORT}/Antigravity IDE/mcp_config.json",
        "{XDG_CONFIG_HOME}/Antigravity IDE/mcp.json",
    ],
    "antigravity-2.0": [
        "{HOME}/.antigravity-2.0/mcp.json",
        "{HOME}/.gemini/antigravity-2.0/mcp_config.json",
        "{HOME}/.gemini/antigravity-2.0/mcp.json",
        "{APP_SUPPORT}/Antigravity 2.0/mcp.json",
        "{XDG_CONFIG_HOME}/Antigravity 2.0/mcp.json",
    ],
    "antigravity-cli": [
        "{HOME}/.antigravity-cli/mcp.json",
        "{HOME}/.gemini/antigravity-cli/mcp_config.json",
        "{HOME}/.gemini/antigravity-cli/mcp.json",
        "{APP_SUPPORT}/Antigravity CLI/mcp.json",
        "{XDG_CONFIG_HOME}/Antigravity CLI/mcp.json",
    ],
}


def _get_platform_base_paths(home):
    system = sys.platform
    app_support = ""
    appdata = ""
    xdg_config = home / ".config"

    if system == "darwin":
        app_support = home / "Library/Application Support"
    elif system == "win32":
        appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
        app_support = appdata
    else:  # linux
        xdg_config_env = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_env:
            xdg_config = Path(xdg_config_env)
        app_support = xdg_config

    return {
        "HOME": home,
        "APP_SUPPORT": app_support,
        "APPDATA": appdata or app_support,  # Fallback for non-windows
        "XDG_CONFIG_HOME": xdg_config,
    }


def get_config_paths(app_name):
    """Calculates all possible, absolute configuration file paths based on the operating system."""

    # Check for direct path input first
    name, direct_target = resolve_custom_entry(app_name)
    if direct_target:
        if direct_target.is_file():
            return [direct_target]
        elif direct_target.is_dir():
            # Scan the given directory
            return discover_config_files_by_content(
                direct_target.name, [direct_target.parent]
            )

    # Check for saved custom apps
    custom_apps = load_custom_apps()
    if name in custom_apps:
        return [Path(p) for p in custom_apps[name]]

    paths = []
    # First, search dynamically for existing files on the system matching the app_name
    dynamic_paths = search_config_paths(app_name)
    if dynamic_paths:
        paths.extend(dynamic_paths)

    home = Path.home()
    base_paths = _get_platform_base_paths(home)
    app_slug = name.lower().replace(" ", "").replace("-", "")

    # Look for a specific template for the app
    clean_name = name.lower().strip()
    if clean_name in PATH_TEMPLATES:
        template_key = clean_name
    elif clean_name.replace(" ", "-") in PATH_TEMPLATES:
        template_key = clean_name.replace(" ", "-")
    elif app_slug in PATH_TEMPLATES:
        template_key = app_slug
    elif "antigravity" in app_slug:
        if "ide" in app_slug:
            template_key = "antigravity-ide"
        elif "2" in app_slug:
            template_key = "antigravity-2.0"
        elif "cli" in app_slug:
            template_key = "antigravity-cli"
        else:
            template_key = "antigravity"
    elif app_slug == "cursoragent":
        template_key = "cursor"
    elif app_slug in ["visualstudiocode", "code"]:
        template_key = "vscode"
    else:
        template_key = app_slug

    path_templates = PATH_TEMPLATES.get(template_key)

    # If no specific template, use the generic fallback
    if not path_templates:
        path_templates = list(PATH_TEMPLATES["default"])
        os_specific_fallbacks = PATH_TEMPLATES.get(sys.platform, {}).get("default", [])
        path_templates.extend(os_specific_fallbacks)

    for template in path_templates:
        path_str = template.format(app=app_slug, app_name=name, **base_paths)
        paths.append(Path(path_str))

    return list(dict.fromkeys(paths))  # Return unique paths


def get_config_path(app_name):
    """Calculates the primary, absolute configuration file path based on the operating system."""
    paths = get_config_paths(app_name)
    if paths:
        return paths[0]

    # Fallback if no paths are generated
    home = Path.home()
    app_slug = app_name.lower().replace(" ", "").replace("-", "")
    return home / f".{app_slug}" / "mcp.json"


WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def sanitize_filename(name: str) -> str:
    """Removes characters that are not allowed in macOS/Windows file names."""
    if not name or not isinstance(name, str):
        return "Untitled_Chat"
    clean = name.replace("\x00", "")
    safe_name = re.sub(r'[\\/*?:"<>|\x00-\x1f]', "_", clean)
    safe_name = re.sub(r"\.{2,}", "_", safe_name)
    safe_name = safe_name.strip(". ")
    if not safe_name:
        return "Untitled_Chat"
    safe_name = safe_name[:100].rstrip(". ")
    if not safe_name:
        return "Untitled_Chat"
    stem = safe_name.split(".")[0].upper()
    if stem in WINDOWS_RESERVED:
        safe_name = f"_{safe_name}"
    return safe_name


def split_export_file(export_file_path, output_dir_path):
    """Parses the single chat export JSON and splits it into individual neat files."""
    export_path = Path(export_file_path).expanduser().resolve()
    out_dir = Path(output_dir_path).expanduser().resolve()

    if not export_path.exists():
        print(
            f"Error: The export file '{export_path}' does not exist.", file=sys.stderr
        )
        return

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(
            f"Error: Could not create output directory '{out_dir}': {e}",
            file=sys.stderr,
        )
        return

    try:
        with open(export_path, "r", encoding="utf-8") as f:
            conversations = json.load(f)

        if isinstance(conversations, dict):
            conversations = conversations.get("conversations", [conversations])
        elif not isinstance(conversations, list):
            conversations = [conversations]

        print(
            f"Parsing '{export_path.name}'... Found {len(conversations)} distinct conversation threads."
        )

        saved_count = 0
        for idx, chat in enumerate(conversations):
            raw_title = chat.get("title") if isinstance(chat, dict) else None
            title_candidate = raw_title.strip() if isinstance(raw_title, str) and raw_title.strip() else f"chat_session_{idx}"
            safe_title = sanitize_filename(title_candidate)
            output_file = out_dir / f"{safe_title}.json"

            try:
                if os.path.commonpath([output_file.resolve(), out_dir.resolve()]) != str(out_dir.resolve()):
                    print(f"Warning: Skipping path traversal candidate: {output_file}", file=sys.stderr)
                    continue
            except ValueError:
                continue

            counter = 1
            while output_file.exists():
                output_file = out_dir / f"{safe_title}_{counter}.json"
                counter += 1

            try:
                with open(output_file, "w", encoding="utf-8") as out_f:
                    json.dump(chat, out_f, indent=2)
                saved_count += 1
            except IOError as e:
                print(
                    f"Warning: Could not write to file {output_file}: {e}",
                    file=sys.stderr,
                )

        print(
            f"Successfully extracted and stored {saved_count} structured chat logs inside: {out_dir}"
        )

    except (json.JSONDecodeError, IOError) as e:
        print(f"Failed to read or parse file '{export_path}': {e}", file=sys.stderr)


def get_mcp_config():
    """Dynamically locates the absolute path of chronicle or uvx to prevent path resolution errors."""
    chronicle_path = shutil.which("chronicle")
    if chronicle_path:
        try:
            with open(chronicle_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line.startswith("#!"):
                    interpreter = first_line[2:].strip()
                    parts = interpreter.split()
                    if parts:
                        cmd = parts[0]
                        args = parts[1:]
                        if "env" in Path(cmd).name and args:
                            real_cmd = shutil.which(args[0])
                            if real_cmd and ("python" in Path(args[0]).name.lower() or Path(real_cmd).resolve() == Path(sys.executable).resolve()):
                                return {
                                    "command": str(real_cmd),
                                    "args": [str(chronicle_path)] + args[1:],
                                }
                        elif Path(cmd).exists() and ("python" in Path(cmd).name.lower() or Path(cmd).resolve() == Path(sys.executable).resolve()):
                            return {
                                "command": str(cmd),
                                "args": [str(chronicle_path)] + args,
                            }
        except (IOError, OSError, UnicodeDecodeError):
            pass  # Non-critical, will use fallback

        return {"command": str(chronicle_path), "args": []}

    uvx_path = shutil.which("uvx")

    if not uvx_path:
        uvx_path = "uvx"

    return {
        "command": str(uvx_path),
        "args": ["--from", "chronicle-mcp-server", "chronicle"],
    }


def update_json_config(app_name):
    """Safely injects the chronicle-mcp configuration into the resolved target application JSON."""
    file_paths = get_config_paths(app_name)
    existing_paths = [p for p in file_paths if p.exists()]
    target_paths = existing_paths if existing_paths else file_paths[:1]
    updated_paths = []

    for file_path in target_paths:
        try:
            # For new files, ensure parent directory exists
            if not file_path.exists():
                try:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    print(
                        f"Warning: Could not create directory {file_path.parent}: {e}",
                        file=sys.stderr,
                    )
                    continue  # Skip if we can't create the directory

            data = _load_json_lenient(file_path)
            if data is None:
                if file_path.exists() and file_path.stat().st_size > 0:
                    bak_file = file_path.with_suffix(file_path.suffix + ".bak")
                    try:
                        shutil.copy2(file_path, bak_file)
                        print(
                            f"Warning: Existing config at {file_path} had syntax errors. Created backup at {bak_file} before updating.",
                            file=sys.stderr,
                        )
                    except Exception as b_err:
                        print(f"Warning: Could not create backup of {file_path}: {b_err}", file=sys.stderr)
                data = {}

            mcp_config = get_mcp_config()

            # Schema detection
            is_opencode = "mcp" in data
            if not is_opencode:  # Fallback to name-based detection
                is_opencode = (
                    file_path.name in ["opencode.json", "opencode.jsonc"]
                    or "opencode" in app_name.lower()
                )

            if is_opencode:
                if "mcp" not in data or not isinstance(data["mcp"], dict):
                    data["mcp"] = {}
                data["mcp"]["chronicle-mcp"] = {
                    "type": "local",
                    "command": [mcp_config["command"]] + mcp_config.get("args", []),
                    "enabled": True,
                }
            else:  # Default to mcpServers
                if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
                    data["mcpServers"] = {}
                data["mcpServers"]["chronicle-mcp"] = mcp_config

            dir_name = file_path.parent
            dir_name.mkdir(parents=True, exist_ok=True)
            fd, tmp_file = tempfile.mkstemp(dir=str(dir_name), prefix=".tmp_mcp_", suffix=".json")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_file, file_path)
            except Exception:
                if os.path.exists(tmp_file):
                    try:
                        os.remove(tmp_file)
                    except OSError:
                        pass
                raise

            print(
                f"Successfully configured chronicle-mcp inside {app_name} at: {file_path}"
            )
            updated_paths.append(file_path)
        except (IOError, OSError) as e:
            print(
                f"Error updating {app_name} configuration at {file_path}: {e}",
                file=sys.stderr,
            )

    if updated_paths:
        # If the app is not a known target, save its path for future use
        name, _ = resolve_custom_entry(app_name)
        if name not in SUPPORTED_TARGETS:
            save_custom_app(name, updated_paths)
    elif not file_paths:
        print(
            f"Error: Could not find or create a config file for {app_name}",
            file=sys.stderr,
        )


def getch():
    import sys

    if sys.platform == "win32":
        try:
            import msvcrt

            ch_bytes = msvcrt.getch()
            if ch_bytes in (b"\x00", b"\xe0"):
                ch_bytes += msvcrt.getch()
                if ch_bytes.endswith(b"H"):
                    return "\x1b[A"  # Up arrow
                elif ch_bytes.endswith(b"P"):
                    return "\x1b[B"  # Down arrow
            return ch_bytes.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    import os
    import select
    import termios
    import tty

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


def select_apps_interactive(error_msgs=None):
    import sys

    if error_msgs is None:
        error_msgs = []

    options = [
        {"id": "cursor", "title": "Cursor", "checked": False},
        {"id": "vscode", "title": "VS Code (Cline / Roo Code)", "checked": False},
        {"id": "trae", "title": "Trae IDE", "checked": False},
        {"id": "claude", "title": "Claude Code", "checked": False},
        {"id": "windsurf", "title": "Windsurf", "checked": False},
        {"id": "claude-desktop", "title": "Claude Desktop", "checked": False},
        {"id": "chatgpt-desktop", "title": "ChatGPT Desktop", "checked": False},
        {"id": "antigravity", "title": "Antigravity", "checked": False},
        {"id": "kiro", "title": "Kiro", "checked": False},
        {"id": "other", "title": "Other (Enter custom entry)", "checked": False},
    ]

    sub_options = [
        {
            "id": "antigravity-ide",
            "title": "Antigravity IDE",
            "checked": False,
            "indent": True,
        },
        {
            "id": "antigravity-2.0",
            "title": "Antigravity 2.0",
            "checked": False,
            "indent": True,
        },
        {
            "id": "antigravity-cli",
            "title": "Antigravity CLI",
            "checked": False,
            "indent": True,
        },
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
    custom_input = ""

    print(
        "\n\033[38;5;99mPlease select the applications/IDEs where you want to install Chronicle MCP:\033[0m"
    )
    print(
        "\033[90m  (Use arrow keys to navigate, Space to toggle, Enter to confirm)\033[0m"
    )

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
                is_focused = idx == cursor_idx
                indent = "    " if item.get("indent") else "  "
                pointer = "\033[38;5;99m❯\033[0m " if is_focused else "  "

                if item["id"] == "other":
                    # Render other app name input inline (no checkbox, aligned with checkbox start)
                    val_color = "\033[1;37m" if is_focused else "\033[37m"
                    text = f"\033[90mOther (Enter custom entry):\033[0m {val_color}{custom_input}\033[0m"
                    lines.append(f"{pointer}{indent}{text}")
                else:
                    if item["checked"]:
                        checked_str = "\033[1;32m[✓]\033[0m"
                    else:
                        checked_str = "\033[90m[ ]\033[0m"

                    if is_focused:
                        text = f"\033[1;37m{item['title']}\033[0m"
                    else:
                        text = f"\033[37m{item['title']}\033[0m"

                    lines.append(f"{pointer}{indent}{checked_str} {text}")

            if error_msgs:
                lines.append("")
                for msg in error_msgs:
                    lines.append(f"\033[33m ⚠ {msg}\033[0m")

            sys.stdout.write("\n".join(lines) + "\n")
            sys.stdout.flush()
            lines_count = len(lines)

            key = getch()
            if key == "\x1b[A":  # Up
                cursor_idx = (cursor_idx - 1) % len(visible_items)
            elif key == "\x1b[B":  # Down
                cursor_idx = (cursor_idx + 1) % len(visible_items)
            elif key == " ":  # Space
                item = visible_items[cursor_idx]
                if item["id"] == "other":
                    custom_input += " "
                else:
                    item["checked"] = not item["checked"]

                    if item["id"] == "antigravity" and not item["checked"]:
                        for sub in sub_options:
                            sub["checked"] = False
                error_msgs = []
            elif key == "\r" or key == "\n":  # Enter
                custom_input_stripped = custom_input.strip()
                if custom_input_stripped:

                    name, direct_target = resolve_custom_entry(custom_input_stripped)

                    if direct_target:  # It's a valid path
                        break

                    if name in SUPPORTED_TARGETS:
                        break

                    # Check if it's discoverable
                    if (
                        search_config_paths(name)
                        or find_executable_or_app(name)
                        or get_config_path(custom_input_stripped).parent.exists()
                    ):
                        break
                    else:
                        error_msgs = [
                            f'App/IDE "{custom_input_stripped}" was not found or is not a valid path.'
                        ]

                else:
                    break
            elif key == "\x03" or key == "\x1b":  # Ctrl+C or Escape
                raise KeyboardInterrupt
            elif len(key) == 1 and 32 <= ord(key) <= 126:
                # Printable ASCII character input
                item = visible_items[cursor_idx]
                if item["id"] == "other":
                    custom_input += key
                    error_msgs = []
            elif key == "\x7f" or key == "\x08":
                # Backspace
                item = visible_items[cursor_idx]
                if item["id"] == "other":
                    custom_input = custom_input[:-1]
                    error_msgs = []
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    return visible_items, custom_input


def print_startup_logo():
    logo = (
        "\n\033[38;5;99m"
        " ████████  ██    ██  ███████   ████████  ██    ██  ██████  ████████  ██        ████████\n"
        "██         ██    ██  ██    ██  ██    ██  ███   ██    ██    ██        ██        ██      \n"
        "██         ████████  ███████   ██    ██  ████  ██    ██    ██        ██        ███████ \n"
        "██         ██    ██  ██   ██   ██    ██  ██ ██ ██    ██    ██        ██        ██      \n"
        " ████████  ██    ██  ██    ██  ████████  ██  ████  ██████  ████████  ████████  ████████\033[0m\n"
        "\n"
        "                         \033[90mYOUR AI FORGETS. CHRONICLE REMEMBERS.\033[0m\n"
    )
    print(logo)


def run_setup_wizard():
    print_startup_logo()
    # Phase 1: The Temporal Split
    print()
    print(
        "\033[38;5;99m── Chronicle Archive Setup ─────────────────────────────────────\033[0m"
    )
    print("Do you want to split a single conversations.json file?")
    export_path_str = input(
        "Enter path to export file (or press ENTER to skip): "
    ).strip()

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
    chats_folder_input = input(
        "Enter path to folder containing your conversations [Default: ~/universal-chats]: "
    ).strip()
    if not chats_folder_input:
        chats_folder_input = "~/universal-chats"

    resolved_storage_path = Path(chats_folder_input).expanduser().resolve()

    dir_existed = resolved_storage_path.exists()
    resolved_storage_path.mkdir(parents=True, exist_ok=True)
    if not dir_existed:
        print(
            f"\033[32m✓ Initialized storage directory: {resolved_storage_path}\033[0m"
        )
    else:
        print(
            f"\033[32m✓ Using existing storage directory: {resolved_storage_path}\033[0m"
        )

    set_chats_folder(resolved_storage_path)
    os.environ["CHRONICLE_BASE_DIR"] = str(resolved_storage_path)

    # Run split if requested and valid
    if split_file_path:
        print(f"Splitting '{split_file_path.name}' into '{resolved_storage_path}'...")
        split_export_file(split_file_path, resolved_storage_path)
        print("\033[32m ✓ Successfully split logs.\033[0m")

    # Phase 3: MCQ
    app_mapping = {
        1: "cursor",
        2: "vscode",
        3: "trae",
        4: "claude",
        5: "windsurf",
        6: "claude-desktop",
        7: "chatgpt-desktop",
        8: "antigravity",
        9: "kiro",
    }

    selected_apps = []
    while True:
        invalid_apps = []
        selected_apps = []

        # Check if tty and termios can be imported for interactive mode
        is_interactive = sys.stdin.isatty()
        try:
            import select
            import termios
            import tty
        except ImportError:
            is_interactive = False

        if is_interactive:
            try:
                visible_items, custom_input = select_apps_interactive()
                for item in visible_items:
                    if item["checked"] and item["id"] != "other":
                        selected_apps.append(item["id"])

                custom_input_stripped = custom_input.strip()
                if custom_input_stripped:
                    name, direct_target = resolve_custom_entry(custom_input_stripped)
                    if direct_target:
                        selected_apps.append(custom_input_stripped)  # Use the raw path
                    elif name in SUPPORTED_TARGETS:
                        selected_apps.append(name)
                    elif search_config_paths(name) or find_executable_or_app(name):
                        selected_apps.append(name)
                    else:
                        invalid_apps.append((custom_input_stripped, "not_found"))
            except KeyboardInterrupt:
                print("\n\033[31mSetup cancelled by user.\033[0m")
                sys.exit(1)
        else:
            # Fallback for non-TTY / tests / Windows automated setups
            print(
                "\n\033[38;5;99mPlease select the applications/IDEs where you want to install Chronicle MCP:\033[0m"
            )
            print("  [1] Cursor")
            print("  [2] VS Code (Cline / Roo Code)")
            print("  [3] Trae IDE")
            print("  [4] Claude Code")
            print("  [5] Windsurf")
            print("  [6] Claude Desktop")
            print("  [7] ChatGPT Desktop")
            print("  [8] Antigravity")
            print("  [9] Kiro")
            print("  [10] Other (Custom Entry)")

            choices_input = input(
                "Enter choices as comma-separated numbers (e.g., 1, 3, 5): "
            ).strip()
            if not choices_input:
                print(
                    "\033[90m → No choices selected. Skipping MCP installation.\033[0m"
                )
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
                        elif num == 10:
                            has_other = True
                        else:
                            invalid_apps.append((part, "not_supported"))
                    else:
                        invalid_apps.append((part, "not_supported"))

                if has_antigravity:
                    selected_apps.append("antigravity")
                    sub_choices = input(
                        "Select Antigravity options: [1] Antigravity IDE, [2] Antigravity 2.0, [3] Antigravity CLI (comma-separated): "
                    ).strip()
                    if sub_choices:
                        sub_parts = [
                            p.strip() for p in sub_choices.split(",") if p.strip()
                        ]
                        sub_mapping = {
                            1: "antigravity-ide",
                            2: "antigravity-2.0",
                            3: "antigravity-cli",
                        }
                        for sp in sub_parts:
                            if sp.isdigit():
                                s_num = int(sp)
                                if s_num in sub_mapping:
                                    selected_apps.append(sub_mapping[s_num])
                                else:
                                    invalid_apps.append(
                                        (f"antigravity-sub-{sp}", "not_supported")
                                    )
                            else:
                                invalid_apps.append((sp, "not_supported"))

                if has_other:
                    custom_entry = input(
                        "Enter the name of your custom application or a full path: "
                    ).strip()
                    if custom_entry:
                        name, direct_target = resolve_custom_entry(custom_entry)
                        if direct_target:
                            selected_apps.append(custom_entry)  # Use the raw path
                        elif name in SUPPORTED_TARGETS:
                            selected_apps.append(name)
                        elif (
                            search_config_paths(name)
                            or find_executable_or_app(name)
                            or get_config_path(custom_entry).parent.exists()
                        ):
                            selected_apps.append(name)
                        else:
                            invalid_apps.append((name, "not_found"))

        selected_apps = list(dict.fromkeys(selected_apps))

        if invalid_apps:
            for inv, err_type in invalid_apps:
                if err_type == "not_found":
                    print(
                        f'\033[33m ⚠ App/IDE "{inv}" was not found on your system.\033[0m'
                    )
                else:
                    print(
                        f'\033[33m ⚠ App/IDE "{inv}" is not currently supported by auto-install.\033[0m'
                    )

            if selected_apps:
                valid_apps_str = ", ".join(selected_apps)
                ans = (
                    input(
                        f"Would you like to proceed with installing to the valid selected applications ({valid_apps_str})? [Y/n]: "
                    )
                    .strip()
                    .lower()
                )
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
        "antigravity-cli": "Antigravity CLI",
        "kiro": "Kiro",
    }

    installed_apps = []
    for app in selected_apps:
        update_json_config(app)
        installed_apps.append(app_titles.get(app, app.title().replace("-", " ")))

    print(
        "\n\033[38;5;99m── Chronicle Environment Live ──────────────────────────────────\033[0m"
    )
    print(f" \033[32m✓\033[0m Storage Folder : {resolved_storage_path}")
    if installed_apps:
        print(
            f" \033[32m✓\033[0m Auto-Saved Configs for: [{', '.join(installed_apps)}]"
        )
    else:
        print(" \033[33m⚠\033[0m No applications configured for auto-save.")
    print("\n  How to run the server manually:")
    print("  $ uvx --from chronicle-mcp-server chronicle")
    print("\n  recalled in <1ms · 100% local · zero cloud")
    print(
        "\033[38;5;99m────────────────────────────────────────────────────────────────\033[0m"
    )


def main():
    # Route to the setup wizard if len(sys.argv) == 1 and sys.stdin.isatty(), or if sys.argv[1] == "setup"
    if (len(sys.argv) == 1 and sys.stdin.isatty()) or (
        len(sys.argv) == 2 and sys.argv[1] == "setup"
    ):
        run_setup_wizard()
        return

    parser = argparse.ArgumentParser(description="Chronicle MCP Command Line Interface")
    parser.add_argument(
        "--chats-folder",
        type=str,
        help="Set the default local storage directory for chat transcripts",
    )

    subparsers = parser.add_subparsers(dest="command")

    # Subcommand: add
    add_parser = subparsers.add_parser(
        "add", help="Add chronicle MCP to a specified application environment"
    )
    add_parser.add_argument(
        "app",
        type=str,
        help="The target application interface name (e.g. cursor, claude, trae, vscode, kiro)",
    )

    # Subcommand: split
    split_parser = subparsers.add_parser(
        "split", help="Split a combined conversation export into separate files"
    )
    split_parser.add_argument(
        "file", type=str, help="Path to the monolithic conversation.json file"
    )
    split_parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Target folder directory to save split chats",
    )

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
