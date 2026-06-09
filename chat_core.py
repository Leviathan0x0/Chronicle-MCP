"""Core business logic for the Universal Chat Connector MCP."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from typing import Any

def get_default_base_dir() -> str:
    if os.environ.get("CHRONICLE_BASE_DIR"):
        return os.environ["CHRONICLE_BASE_DIR"]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(script_dir, ".git")):
        return script_dir
    return os.path.expanduser("~/.chronicle")


def resolve_default_transcripts_dir(client: str) -> str:
    if os.environ.get("TRANSCRIPTS_DIR"):
        return os.environ["TRANSCRIPTS_DIR"]
    home = os.path.expanduser("~")
    if client == "cursor":
        cursor_projects_dir = os.path.join(home, ".cursor", "projects")
        if os.path.isdir(cursor_projects_dir):
            transcripts_dirs = []
            try:
                for d in os.listdir(cursor_projects_dir):
                    proj_path = os.path.join(cursor_projects_dir, d)
                    if os.path.isdir(proj_path):
                        trans_path = os.path.join(proj_path, "agent-transcripts")
                        if os.path.isdir(trans_path):
                            transcripts_dirs.append((trans_path, os.path.getmtime(trans_path)))
            except Exception:
                pass
            if transcripts_dirs:
                transcripts_dirs.sort(key=lambda x: x[1], reverse=True)
                return transcripts_dirs[0][0]
        return os.path.join(home, ".cursor-transcripts")
    elif client == "continue":
        continue_dir = os.path.join(home, ".continue", "dev_data", "history")
        if os.path.isdir(continue_dir):
            return continue_dir
        return os.path.join(home, ".continue-transcripts")
    elif client == "cline":
        vscode_dirs = [
            os.path.join(home, "Library", "Application Support", "Code", "User", "globalStorage", "saoudrizwan.claude-dev", "settings"),
            os.path.join(home, ".config", "Code", "User", "globalStorage", "saoudrizwan.claude-dev", "settings"),
        ]
        for d in vscode_dirs:
            if os.path.isdir(d):
                return d
        return os.path.join(home, ".cline-transcripts")
    elif client == "copilot":
        return os.path.join(home, ".copilot-transcripts")
    return os.path.join(home, f".{client}-transcripts")


def parse_external_transcript(file_path: str) -> list[dict] | None:
    """Parse an external transcript file (JSON, JSONL, or MD) into standard messages."""
    if file_path.endswith(".jsonl"):
        messages = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    if isinstance(entry, dict):
                        role = entry.get("role") or entry.get("sender") or "user"
                        content = entry.get("content") or entry.get("text") or ""
                        if content:
                            messages.append({"role": str(role), "content": str(content)})
            return messages if messages else None
        except Exception:
            return None

    elif file_path.endswith(".json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                messages = []
                for item in data:
                    if isinstance(item, dict):
                        role = item.get("role") or item.get("sender") or "user"
                        content = item.get("content") or item.get("text") or ""
                        if content:
                            messages.append({"role": str(role), "content": str(content)})
                return messages if messages else None
            elif isinstance(data, dict):
                for key in ["messages", "history", "chat_messages", "sessions"]:
                    if key in data and isinstance(data[key], list):
                        messages = []
                        for item in data[key]:
                            if isinstance(item, dict):
                                role = item.get("role") or item.get("sender") or "user"
                                content = item.get("content") or item.get("text") or ""
                                if content:
                                    messages.append({"role": str(role), "content": str(content)})
                        return messages if messages else None
        except Exception:
            return None

    elif file_path.endswith(".md"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            lines = text.splitlines()
            messages = []
            current_role = None
            current_content = []
            for line in lines:
                role_match = re.match(
                    r"^(?:\#+\s*|[\*\#\_\s]*)(User|Assistant|System|Human|AI)[\*\#\_\s]*[:\-]?\s*$",
                    line,
                    re.IGNORECASE,
                )
                if role_match:
                    if current_role and current_content:
                        messages.append({
                            "role": current_role,
                            "content": "\n".join(current_content).strip(),
                        })
                    role_str = role_match.group(1).lower()
                    if role_str in ["user", "human"]:
                        current_role = "user"
                    elif role_str in ["assistant", "ai"]:
                        current_role = "assistant"
                    else:
                        current_role = "system"
                    current_content = []
                else:
                    if current_role:
                        current_content.append(line)
            if current_role and current_content:
                messages.append({
                    "role": current_role,
                    "content": "\n".join(current_content).strip(),
                })
            return messages if messages else None
        except Exception:
            return None
    return None


DEFAULT_BASE_DIR = get_default_base_dir()
DEFAULT_CURSOR_TRANSCRIPTS = resolve_default_transcripts_dir("cursor")


TOPIC_KEYWORDS: dict[str, list[str]] = {
    "mcp": ["mcp", "model context protocol", "connector", "stdio"],
    "ui_design": ["ui", "ux", "landing page", "navbar", "hero", "css", "tailwind"],
    "roblox": ["roblox", "luau", "avatar", "game dev"],
    "ai_agents": ["agent", "workflow", "n8n", "prompt", "llm"],
    "school": ["school", "exam", "homework", "chapter", "essay"],
    "coding": ["react", "python", "typescript", "api", "backend", "frontend"],
}

ACTION_PATTERNS = [
    re.compile(r"(?i)\bTODO[:\s]+(.+?)(?:\n|$)"),
    re.compile(r"(?i)\baction item[:\s]+(.+?)(?:\n|$)"),
    re.compile(r"(?i)^\s*[-*]\s*\[ \]\s*(.+?)(?:\n|$)", re.MULTILINE),
    re.compile(r"(?i)^\s*\d+\.\s*(implement|fix|add|create|build|update|remove)\s+(.+?)(?:\n|$)", re.MULTILINE),
]


def sanitize_filename(name: str) -> str:
    safe_name = re.sub(r'[\\/*?:"<>| ]', "_", name)
    return safe_name.strip()[:50]


def parse_to_plain_text(chat_data: dict | list) -> list[str]:
    """Normalize ChatGPT, Claude, Gemini, and flat JSON exports to plain text."""
    messages: list[str] = []

    if isinstance(chat_data, dict) and "mapping" in chat_data:
        nodes = []
        for _node_id, node in chat_data.get("mapping", {}).items():
            message = node.get("message")
            if message and message.get("author") and message.get("content"):
                role = message["author"]["role"]
                if role in ["user", "assistant", "system", "model"]:
                    parts = message["content"].get("parts", [""])
                    text = " ".join(p for p in parts if isinstance(p, str))
                    if text.strip():
                        nodes.append({
                            "role": role,
                            "text": text.strip(),
                            "create_time": message.get("create_time") or 0,
                        })
        nodes.sort(key=lambda x: x["create_time"])
        for node in nodes:
            prefix = _role_prefix(node["role"])
            messages.append(f"{prefix}{node['text']}")
    elif isinstance(chat_data, dict) and "chat_messages" in chat_data:
        for msg in chat_data.get("chat_messages", []):
            if not isinstance(msg, dict):
                continue
            sender = msg.get("sender", "human")
            role = "user" if str(sender).lower() in ["human", "user"] else "assistant"
            text = msg.get("text", "")
            if not text.strip() and isinstance(msg.get("content"), list):
                text = " ".join(
                    part.get("text", "")
                    for part in msg["content"]
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            if text.strip():
                messages.append(f"{_role_prefix(role)}{text.strip()}")
    elif (isinstance(chat_data, dict) and "messages" in chat_data) or isinstance(chat_data, list):
        raw_msgs = chat_data.get("messages", chat_data) if isinstance(chat_data, dict) else chat_data
        for msg in raw_msgs:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role") or msg.get("author", {}).get("role") or msg.get("sender") or "user"
            role_str = str(role).lower()
            if role_str in ["human", "user", "u"]:
                role = "user"
            elif role_str in ["assistant", "model", "ai", "a"]:
                role = "assistant"
            content = msg.get("content") or msg.get("text") or ""
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict):
                        text_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        text_parts.append(part)
                text = " ".join(text_parts)
            else:
                text = str(content)
            if text.strip():
                prefix = _role_prefix(str(role))
                messages.append(f"{prefix}{text.strip()}")

    return messages


def _role_prefix(role: str) -> str:
    role_lower = role.lower()
    if role_lower in ["user", "human", "u"]:
        return "U: "
    if role_lower in ["assistant", "model", "ai", "a"]:
        return "A: "
    return "System: "


def summarize_text_code_blocks(text: str) -> str:
    pattern = re.compile(r"```([a-zA-Z0-9+#_-]*)\s*\n(.*?)\n\s*```", re.DOTALL)

    def replacer(match):
        lang = match.group(1).strip() or "text"
        code = match.group(2)
        lines_count = len(code.splitlines())
        return f"\n[Code Block: {lang}, {lines_count} lines. Re-run tool with summarize_code=False to view full code]\n"

    return pattern.sub(replacer, text)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]{3,}", text.lower())


def _tfidf_vectors(docs: list[str]) -> tuple[list[Counter[str]], Counter[str]]:
    tokenized = [_tokenize(doc) for doc in docs]
    df: Counter[str] = Counter()
    for tokens in tokenized:
        df.update(set(tokens))
    n = len(docs)
    vectors: list[Counter[str]] = []
    for tokens in tokenized:
        tf = Counter(tokens)
        vec: Counter[str] = Counter()
        for term, count in tf.items():
            idf = math.log((n + 1) / (df[term] + 1)) + 1
            vec[term] = count * idf
        vectors.append(vec)
    return vectors, df


def _cosine_similarity(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class ChatConnector:
    def __init__(self, base_dir: str | None = None, cursor_transcripts_dir: str | None = None):
        self.base_dir = base_dir or DEFAULT_BASE_DIR
        self.chats_dir = os.path.join(self.base_dir, "chats")
        self.exports_dir = os.path.join(self.base_dir, "exports")
        self.config_path = os.path.join(self.base_dir, "mcp_config.json")
        self.watch_state_path = os.path.join(self.base_dir, ".watch_state.json")
        self.index_path = os.path.join(self.base_dir, "knowledge_index.json")
        self.cursor_transcripts_dir = cursor_transcripts_dir or DEFAULT_CURSOR_TRANSCRIPTS
        self._pending_session: dict[str, Any] | None = None
        os.makedirs(self.chats_dir, exist_ok=True)
        os.makedirs(self.exports_dir, exist_ok=True)

    # ── Config ──────────────────────────────────────────────────────────────

    def load_config(self) -> dict:
        default_config = {
            "auto_save_message_threshold": 20,
            "client_paths": {
                "default": "chats",
                "cursor": "chats/cursor",
                "chatgpt": "chats/chatgpt",
                "claude": "chats/claude",
            },
            "compression_days_threshold": 30,
            "cursor_transcripts_dir": self.cursor_transcripts_dir,
            "transcripts_dirs": {
                c: resolve_default_transcripts_dir(c)
                for c in ["cursor", "continue", "cline", "copilot"]
            },
            "notes": "Change settings via configure_connector_settings tool.",
        }
        if not os.path.exists(self.config_path):
            self._write_json(self.config_path, default_config)
            return default_config
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            for key, value in default_config.items():
                config.setdefault(key, value)
            return config
        except Exception:
            return default_config

    def save_config(self, updates: dict) -> dict:
        config = self.load_config()
        config.update(updates)
        self._write_json(self.config_path, config)
        return config

    def resolve_chats_dir(self, client: str = "default") -> str:
        config = self.load_config()
        rel = config.get("client_paths", {}).get(client, "chats")
        path = os.path.join(self.base_dir, rel)
        os.makedirs(path, exist_ok=True)
        return path

    # ── Security / IO ───────────────────────────────────────────────────────

    def _safe_chat_path(self, file_name: str, client: str = "default") -> str | None:
        if ".." in file_name or file_name.startswith("/"):
            return None
        chats_dir = self.resolve_chats_dir(client)
        file_name = os.path.basename(file_name)
        if not file_name.endswith(".json"):
            file_name = f"{file_name}.json" if not file_name.endswith(".json.gz") else file_name
        file_path = os.path.join(chats_dir, file_name)
        if not os.path.abspath(file_path).startswith(os.path.abspath(chats_dir)):
            return None
        return file_path

    def _read_chat_file(self, file_path: str) -> dict | list:
        if file_path.endswith(".gz"):
            with gzip.open(file_path, "rt", encoding="utf-8") as f:
                return json.load(f)
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: str, data: Any) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _list_json_files(self, client: str = "default") -> list[str]:
        chats_dir = self.resolve_chats_dir(client)
        return sorted(
            f for f in os.listdir(chats_dir)
            if f.endswith(".json") or f.endswith(".json.gz")
        )

    def _file_mtime_iso(self, path: str) -> str:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── Original tools ────────────────────────────────────────────────────────

    def list_all_stored_chats(
        self, page: int = 1, per_page: int = 50, client: str = "default"
    ) -> list[str]:
        try:
            files = self._list_json_files(client)
            if not files:
                return ["No stored chats found."]
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated = files[start_idx:end_idx]
            if not paginated:
                return [f"Page {page} is empty. Total stored chats: {len(files)}."]
            total_pages = (len(files) + per_page - 1) // per_page
            header = f"[Page {page} of {total_pages} (Total chats: {len(files)})]"
            return [header] + paginated
        except Exception as e:
            return [f"Error listing files: {e}"]

    def search_chats_by_keywords(
        self, keywords: list[str], limit: int = 50, client: str = "default"
    ) -> list[str]:
        matching_files: list[tuple[str, int]] = []
        try:
            for file in self._list_json_files(client):
                file_path = os.path.join(self.resolve_chats_dir(client), file)
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().lower()
                match_count = sum(1 for kw in keywords if kw.lower() in content)
                if match_count >= 1:
                    matching_files.append((file, match_count))
            matching_files.sort(key=lambda x: x[1], reverse=True)
            results = [item[0] for item in matching_files]
            if not results:
                return ["No matching conversations found."]
            if len(results) > limit:
                return results[:limit] + [
                    f"[System Note: Truncated to first {limit} matches. Specify a higher limit if needed]"
                ]
            return results
        except Exception as e:
            return [f"Search error: {e}"]

    def read_chat_message_range(
        self,
        file_name: str,
        start_msg: int = 1,
        end_msg: int = 20,
        max_msg_len: int = 1000,
        summarize_code: bool = True,
        client: str = "default",
    ) -> str:
        file_path = self._safe_chat_path(file_name, client)
        if not file_path:
            return "Error: Security block. Access denied."
        if not os.path.exists(file_path):
            return f"File {file_name} not found."
        try:
            raw_data = self._read_chat_file(file_path)
            plain_messages = parse_to_plain_text(raw_data)
            total_msgs = len(plain_messages)
            if total_msgs == 0:
                return "This file contains no extractable conversation messages."
            s_idx = max(0, start_msg - 1)
            e_idx = min(total_msgs, end_msg)
            processed_messages = []
            for msg in plain_messages[s_idx:e_idx]:
                prefix_match = re.match(r"^(U: |A: |System: )", msg)
                prefix = prefix_match.group(0) if prefix_match else ""
                content = msg[len(prefix):]
                if summarize_code:
                    content = summarize_text_code_blocks(content)
                if max_msg_len > 0 and len(content) > max_msg_len:
                    content = (
                        content[:max_msg_len]
                        + f"\n... [Truncated {len(content) - max_msg_len} characters for token efficiency. Re-run read_chat_message_range with max_msg_len=0 or a larger limit to view full content] ..."
                    )
                processed_messages.append(prefix + content)
            output = (
                f"--- Showing Messages {start_msg} to {e_idx} of {total_msgs} total messages ---\n"
                f"[Token efficiency active: summarize_code={summarize_code}, max_msg_len={max_msg_len}]\n\n"
                + "\n".join(processed_messages)
            )
            if e_idx < total_msgs:
                output += f"\n\n[System Note: More messages available. Next chunk starts at message {e_idx + 1}]"
            return output
        except Exception as e:
            return f"Error reading range: {e}"

    def save_current_conversation_state(
        self,
        conversation_name: str,
        messages: list[dict],
        force_save: bool = False,
        client: str = "default",
    ) -> str:
        config = self.load_config()
        threshold = config.get("auto_save_message_threshold", 20)
        count = len(messages)
        self._pending_session = {
            "conversation_name": conversation_name,
            "messages": messages,
            "client": client,
        }
        if count < threshold and not force_save:
            return f"Session not saved. Current count ({count}) is below threshold ({threshold})."
        return self._persist_conversation(conversation_name, messages, client)

    def _persist_conversation(self, conversation_name: str, messages: list[dict], client: str) -> str:
        safe_name = sanitize_filename(conversation_name)
        file_name = f"{safe_name}.json"
        file_path = os.path.join(self.resolve_chats_dir(client), file_name)
        payload = {"title": conversation_name, "messages": messages, "saved_at": self._now_iso()}
        try:
            self._write_json(file_path, payload)
            self._pending_session = None
            return f"Successfully saved state to {file_name} ({len(messages)} messages logged)."
        except Exception as e:
            return f"Error writing file: {e}"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── High impact tools ───────────────────────────────────────────────────

    def delete_stored_chat(self, file_name: str, confirm: bool = False, client: str = "default") -> str:
        if not confirm:
            return "Deletion blocked. Set confirm=true to permanently delete the chat archive."
        file_path = self._safe_chat_path(file_name, client)
        if not file_path:
            return "Error: Security block. Access denied."
        if not os.path.exists(file_path):
            return f"File {file_name} not found."
        try:
            os.remove(file_path)
            return f"Deleted {os.path.basename(file_path)}."
        except Exception as e:
            return f"Delete error: {e}"

    def get_chat_metadata(self, file_name: str, client: str = "default") -> dict:
        file_path = self._safe_chat_path(file_name, client)
        if not file_path or not os.path.exists(file_path):
            return {"error": f"File {file_name} not found."}
        try:
            raw = self._read_chat_file(file_path)
            plain = parse_to_plain_text(raw)
            title = raw.get("title", os.path.splitext(file_name)[0]) if isinstance(raw, dict) else file_name
            return {
                "file_name": os.path.basename(file_path),
                "title": title,
                "message_count": len(plain),
                "file_size_bytes": os.path.getsize(file_path),
                "last_modified": self._file_mtime_iso(file_path),
                "saved_at": raw.get("saved_at") if isinstance(raw, dict) else None,
                "client": client,
            }
        except Exception as e:
            return {"error": str(e)}

    def merge_conversation_into_archive(
        self, file_name: str, new_messages: list[dict], client: str = "default"
    ) -> str:
        file_path = self._safe_chat_path(file_name, client)
        if not file_path:
            return "Error: Security block. Access denied."
        existing: dict = {"title": file_name, "messages": []}
        if os.path.exists(file_path):
            existing = self._read_chat_file(file_path)
            if not isinstance(existing, dict):
                existing = {"title": file_name, "messages": existing}
        merged = existing.get("messages", []) + new_messages
        existing["messages"] = merged
        existing["merged_at"] = self._now_iso()
        self._write_json(file_path, existing)
        return f"Merged {len(new_messages)} messages into {os.path.basename(file_path)} (total: {len(merged)})."

    def export_chat_as_markdown(
        self, file_name: str, output_name: str | None = None, client: str = "default"
    ) -> str:
        file_path = self._safe_chat_path(file_name, client)
        if not file_path or not os.path.exists(file_path):
            return f"File {file_name} not found."
        try:
            raw = self._read_chat_file(file_path)
            title = raw.get("title", os.path.splitext(file_name)[0]) if isinstance(raw, dict) else file_name
            plain = parse_to_plain_text(raw)
            md_name = output_name or f"{os.path.splitext(os.path.basename(file_name))[0]}.md"
            md_path = os.path.join(self.exports_dir, os.path.basename(md_name))
            lines = [f"# {title}", "", f"_Exported: {self._now_iso()}_", ""]
            for msg in plain:
                if msg.startswith("U: "):
                    lines += ["## User", "", msg[3:], ""]
                elif msg.startswith("A: "):
                    lines += ["## Assistant", "", msg[3:], ""]
                else:
                    lines += ["## System", "", msg.split(": ", 1)[-1], ""]
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return f"Exported markdown to exports/{os.path.basename(md_path)} ({len(plain)} messages)."
        except Exception as e:
            return f"Export error: {e}"

    # ── Search and retrieval ────────────────────────────────────────────────

    def search_chats_semantic(self, query: str, top_k: int = 10, client: str = "default") -> list[dict]:
        files = self._list_json_files(client)
        if not files:
            return [{"file": "No stored chats found.", "score": 0}]
        docs: list[str] = []
        names: list[str] = []
        chats_dir = self.resolve_chats_dir(client)
        for file in files:
            path = os.path.join(chats_dir, file)
            try:
                raw = self._read_chat_file(path)
                text = " ".join(parse_to_plain_text(raw))
                docs.append(text or file)
                names.append(file)
            except Exception:
                docs.append(file)
                names.append(file)
        vectors, _ = _tfidf_vectors(docs)
        query_vec = _tfidf_vectors([query])[0][0]
        scored = [
            {"file": name, "score": round(_cosine_similarity(query_vec, vec), 4)}
            for name, vec in zip(names, vectors)
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def get_chat_summary(self, file_name: str, client: str = "default") -> str:
        file_path = self._safe_chat_path(file_name, client)
        if not file_path or not os.path.exists(file_path):
            return f"File {file_name} not found."
        try:
            raw = self._read_chat_file(file_path)
            plain = parse_to_plain_text(raw)
            if not plain:
                return "No messages to summarize."
            title = raw.get("title", file_name) if isinstance(raw, dict) else file_name
            if isinstance(raw, dict) and raw.get("summary"):
                return f"**{title}** ({len(plain)} messages)\n\n{raw['summary']}"
            user_msgs = [m[3:] for m in plain if m.startswith("U: ")]
            asst_msgs = [m[3:] for m in plain if m.startswith("A: ")]
            opener = user_msgs[0][:300] if user_msgs else plain[0][:300]
            closer = asst_msgs[-1][:300] if asst_msgs else plain[-1][:300]
            return (
                f"**{title}** — {len(plain)} messages\n\n"
                f"Opens with: {opener}{'...' if len(opener) == 300 else ''}\n\n"
                f"Latest: {closer}{'...' if len(closer) == 300 else ''}"
            )
        except Exception as e:
            return f"Summary error: {e}"

    def find_related_chats(self, file_name: str, top_k: int = 5, client: str = "default") -> list[dict]:
        file_path = self._safe_chat_path(file_name, client)
        if not file_path or not os.path.exists(file_path):
            return [{"file": f"File {file_name} not found.", "score": 0}]
        try:
            raw = self._read_chat_file(file_path)
            query = " ".join(parse_to_plain_text(raw))
            results = self.search_chats_semantic(query, top_k=top_k + 1, client=client)
            return [r for r in results if r["file"] != os.path.basename(file_path)][:top_k]
        except Exception as e:
            return [{"file": f"Error: {e}", "score": 0}]

    def filter_chats_by_date_range(
        self, start_date: str, end_date: str, limit: int = 50, client: str = "default"
    ) -> list[dict]:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end = datetime.strptime(end_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        except ValueError:
            return [{"error": "Dates must be YYYY-MM-DD format."}]
        results = []
        chats_dir = self.resolve_chats_dir(client)
        for file in self._list_json_files(client):
            path = os.path.join(chats_dir, file)
            mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
            if start <= mtime <= end:
                results.append({
                    "file_name": file,
                    "last_modified": mtime.strftime("%Y-%m-%dT%H:%M:%SZ"),
                })
        if not results:
            return [{"info": "No chats found in date range."}]
        if len(results) > limit:
            return results[:limit] + [
                {
                    "info": f"Truncated to first {limit} matches. Specify a higher limit if needed."
                }
            ]
        return results

    # ── Automation and workflows ──────────────────────────────────────────────

    def register_session_for_auto_save(
        self, conversation_name: str, messages: list[dict], client: str = "default"
    ) -> str:
        self._pending_session = {
            "conversation_name": conversation_name,
            "messages": messages,
            "client": client,
        }
        return f"Session '{conversation_name}' registered ({len(messages)} messages pending auto-save)."

    def trigger_auto_save_on_session_end(self) -> str:
        if not self._pending_session:
            return "No pending session to auto-save."
        session = self._pending_session
        return self._persist_conversation(
            session["conversation_name"], session["messages"], session.get("client", "default")
        )

    def watch_chats_folder(self, client: str = "default") -> dict:
        chats_dir = self.resolve_chats_dir(client)
        current: dict[str, float] = {}
        for file in self._list_json_files(client):
            path = os.path.join(chats_dir, file)
            current[file] = os.path.getmtime(path)
        previous: dict[str, float] = {}
        if os.path.exists(self.watch_state_path):
            try:
                with open(self.watch_state_path, "r", encoding="utf-8") as f:
                    previous = json.load(f).get(client, {})
            except Exception:
                previous = {}
        new_files = [f for f in current if f not in previous]
        modified = [f for f in current if f in previous and current[f] != previous[f]]
        deleted = [f for f in previous if f not in current]
        all_states = {}
        if os.path.exists(self.watch_state_path):
            try:
                with open(self.watch_state_path, "r", encoding="utf-8") as f:
                    all_states = json.load(f)
            except Exception:
                pass
        all_states[client] = current
        self._write_json(self.watch_state_path, all_states)
        return {
            "new_files": new_files,
            "modified_files": modified,
            "deleted_files": deleted,
            "total_tracked": len(current),
        }

    def import_chat_from_content(
        self, title: str, content: str | dict | list, client: str = "default"
    ) -> str:
        try:
            if isinstance(content, str):
                data = json.loads(content)
            else:
                data = content
            if isinstance(data, dict) and "messages" not in data and "mapping" not in data:
                data = {"title": title, "messages": data if isinstance(data, list) else [data]}
            elif isinstance(data, list):
                data = {"title": title, "messages": data}
            elif isinstance(data, dict) and "title" not in data:
                data["title"] = title
            safe = sanitize_filename(title)
            path = os.path.join(self.resolve_chats_dir(client), f"{safe}.json")
            data["imported_at"] = self._now_iso()
            self._write_json(path, data)
            return f"Imported chat as {safe}.json ({len(parse_to_plain_text(data))} messages)."
        except Exception as e:
            return f"Import error: {e}"

    def import_chat_from_local_path(self, source_path: str, title: str | None = None, client: str = "default") -> str:
        if not os.path.exists(source_path):
            return f"Source path not found: {source_path}"
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            chat_title = title or os.path.splitext(os.path.basename(source_path))[0]
            return self.import_chat_from_content(chat_title, data, client)
        except Exception as e:
            return f"Import error: {e}"

    def sync_agent_transcripts(
        self, client: str, source_dir: str | None = None, limit: int = 50
    ) -> dict:
        config = self.load_config()
        if source_dir:
            src_dir = source_dir
        else:
            src_dir = config.get("transcripts_dirs", {}).get(client) or resolve_default_transcripts_dir(client)
        if not os.path.isdir(src_dir):
            return {
                "error": f"Transcripts directory for '{client}' not found: {src_dir}",
                "imported": [],
            }
        imported = []
        errors = []
        try:
            candidates = sorted(
                [f for f in os.listdir(src_dir) if f.endswith((".json", ".jsonl", ".md"))],
                key=lambda f: os.path.getmtime(os.path.join(src_dir, f)),
                reverse=True,
            )[:limit]
        except Exception as e:
            return {"error": f"Failed to list transcripts: {e}", "imported": []}
        for file in candidates:
            src_path = os.path.join(src_dir, file)
            try:
                messages = parse_external_transcript(src_path)
                if not messages:
                    continue
                title = f"{client}_{os.path.splitext(file)[0][:40]}"
                dest_name = sanitize_filename(title)
                dest = os.path.join(self.resolve_chats_dir(client), f"{dest_name}.json")
                if os.path.exists(dest):
                    imported.append({"file": file, "status": "skipped_exists"})
                    continue
                payload = {
                    "title": title,
                    "messages": messages,
                    "source": f"{client}_agent_transcript",
                    "synced_at": self._now_iso(),
                }
                self._write_json(dest, payload)
                imported.append({
                    "file": file,
                    "status": "imported",
                    "dest": f"{dest_name}.json",
                })
            except Exception as e:
                errors.append({"file": file, "error": str(e)})
        return {"imported": imported, "errors": errors, "total_scanned": len(candidates)}

    def sync_cursor_agent_transcripts(self, limit: int = 50) -> dict:
        """Deprecated: use sync_agent_transcripts(client='cursor') instead."""
        config = self.load_config()
        cursor_override = config.get("cursor_transcripts_dir")
        if cursor_override and cursor_override != DEFAULT_CURSOR_TRANSCRIPTS:
            return self.sync_agent_transcripts("cursor", source_dir=cursor_override, limit=limit)
        return self.sync_agent_transcripts("cursor", limit=limit)

    # ── Intelligence layer ──────────────────────────────────────────────────

    def extract_action_items(self, file_name: str, client: str = "default") -> list[str]:
        file_path = self._safe_chat_path(file_name, client)
        if not file_path or not os.path.exists(file_path):
            return [f"File {file_name} not found."]
        try:
            raw = self._read_chat_file(file_path)
            text = "\n".join(parse_to_plain_text(raw))
            items: list[str] = []
            for pattern in ACTION_PATTERNS:
                for match in pattern.finditer(text):
                    groups = [g.strip() for g in match.groups() if g and g.strip()]
                    if groups:
                        items.append(" ".join(groups))
            return list(dict.fromkeys(items)) or ["No action items detected."]
        except Exception as e:
            return [f"Error: {e}"]

    def build_knowledge_index(
        self, rebuild: bool = False, summary_only: bool = False, client: str = "default"
    ) -> dict:
        if not rebuild and os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    index = json.load(f)
                    if summary_only:
                        return self._summarize_index(index)
                    return index
            except Exception:
                pass
        index: dict[str, list[str]] = {topic: [] for topic in TOPIC_KEYWORDS}
        index["untagged"] = []
        chats_dir = self.resolve_chats_dir(client)
        for file in self._list_json_files(client):
            path = os.path.join(chats_dir, file)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().lower()
                tagged = False
                for topic, keywords in TOPIC_KEYWORDS.items():
                    if any(kw in content for kw in keywords):
                        index[topic].append(file)
                        tagged = True
                if not tagged:
                    index["untagged"].append(file)
            except Exception:
                index["untagged"].append(file)
        index["built_at"] = self._now_iso()
        self._write_json(self.index_path, index)
        if summary_only:
            return self._summarize_index(index)
        return index

    def _summarize_index(self, index: dict) -> dict:
        summary = {
            topic: len(files)
            for topic, files in index.items()
            if topic not in ["built_at", "untagged"]
        }
        summary["untagged"] = len(index.get("untagged", []))
        summary["built_at"] = index.get("built_at", "")
        summary["note"] = (
            "To retrieve the full file lists for a topic, rebuild/run without summary_only=True"
        )
        return summary

    def compare_two_chats(self, file_name_a: str, file_name_b: str, client: str = "default") -> str:
        def keywords_for(file_name: str) -> set[str]:
            path = self._safe_chat_path(file_name, client)
            if not path or not os.path.exists(path):
                return set()
            raw = self._read_chat_file(path)
            return set(_tokenize(" ".join(parse_to_plain_text(raw))))

        kw_a = keywords_for(file_name_a)
        kw_b = keywords_for(file_name_b)
        if not kw_a or not kw_b:
            return "One or both files not found or empty."
        shared = sorted(kw_a & kw_b)[:30]
        only_a = sorted(kw_a - kw_b)[:20]
        only_b = sorted(kw_b - kw_a)[:20]
        meta_a = self.get_chat_metadata(file_name_a, client)
        meta_b = self.get_chat_metadata(file_name_b, client)
        return (
            f"## Compare: {file_name_a} vs {file_name_b}\n\n"
            f"**A:** {meta_a.get('message_count', '?')} msgs | **B:** {meta_b.get('message_count', '?')} msgs\n\n"
            f"**Shared topics:** {', '.join(shared) or 'none'}\n\n"
            f"**Unique to A:** {', '.join(only_a) or 'none'}\n\n"
            f"**Unique to B:** {', '.join(only_b) or 'none'}"
        )

    def generate_project_brief_from_chats(
        self, file_names: list[str], brief_title: str = "Project Brief", client: str = "default"
    ) -> str:
        sections = [f"# {brief_title}", f"_Generated: {self._now_iso()}_", ""]
        for file_name in file_names:
            meta = self.get_chat_metadata(file_name, client)
            summary = self.get_chat_summary(file_name, client)
            actions = self.extract_action_items(file_name, client)
            sections += [
                f"## {meta.get('title', file_name)}",
                f"- File: `{file_name}`",
                f"- Messages: {meta.get('message_count', '?')}",
                f"- Modified: {meta.get('last_modified', '?')}",
                "",
                summary,
                "",
                "**Action items:**",
                *[f"- {a}" for a in actions if not a.startswith("No action") and not a.startswith("File")],
                "",
            ]
        brief_path = os.path.join(self.exports_dir, f"{sanitize_filename(brief_title)}.md")
        text = "\n".join(sections)
        with open(brief_path, "w", encoding="utf-8") as f:
            f.write(text)
        return f"Brief written to exports/{os.path.basename(brief_path)} ({len(file_names)} chats combined)."

    # ── Config and ops ──────────────────────────────────────────────────────

    def configure_connector_settings(self, settings: dict) -> str:
        allowed = {
            "auto_save_message_threshold",
            "client_paths",
            "compression_days_threshold",
            "cursor_transcripts_dir",
            "transcripts_dirs",
        }
        updates = {k: v for k, v in settings.items() if k in allowed}
        if not updates:
            return f"No valid settings provided. Allowed keys: {sorted(allowed)}"
        self.save_config(updates)
        return f"Updated settings: {list(updates.keys())}"

    def compress_old_chat_archives(self, days_old: int | None = None, client: str = "default") -> dict:
        config = self.load_config()
        threshold_days = days_old or config.get("compression_days_threshold", 30)
        cutoff = datetime.now(timezone.utc).timestamp() - (threshold_days * 86400)
        chats_dir = self.resolve_chats_dir(client)
        compressed = []
        skipped = []
        for file in self._list_json_files(client):
            if file.endswith(".gz"):
                continue
            path = os.path.join(chats_dir, file)
            if os.path.getmtime(path) < cutoff:
                gz_path = path + ".gz"
                with open(path, "rb") as f_in:
                    with gzip.open(gz_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(path)
                compressed.append(file)
            else:
                skipped.append(file)
        return {
            "compressed": compressed,
            "skipped_recent": len(skipped),
            "days_threshold": threshold_days,
        }

    def deduplicate_stored_chats(self, dry_run: bool = True, client: str = "default") -> dict:
        chats_dir = self.resolve_chats_dir(client)
        hashes: dict[str, str] = {}
        duplicates: list[dict] = []
        for file in self._list_json_files(client):
            path = os.path.join(chats_dir, file)
            try:
                with open(path, "rb") as f:
                    digest = hashlib.sha256(f.read()).hexdigest()
                if digest in hashes:
                    duplicates.append({"file": file, "duplicate_of": hashes[digest]})
                    if not dry_run:
                        os.remove(path)
                else:
                    hashes[digest] = file
            except Exception as e:
                duplicates.append({"file": file, "error": str(e)})
        return {
            "dry_run": dry_run,
            "duplicates": duplicates,
            "unique_count": len(hashes),
        }

    def get_server_capabilities(self) -> dict:
        return {
            "server": "Universal Chat Connector",
            "transports": ["stdio"],
            "tool_categories": {
                "core": [
                    "list_all_stored_chats",
                    "search_chats_by_keywords",
                    "read_chat_message_range",
                    "save_current_conversation_state",
                ],
                "high_impact": [
                    "delete_stored_chat",
                    "get_chat_metadata",
                    "merge_conversation_into_archive",
                    "export_chat_as_markdown",
                ],
                "search_retrieval": [
                    "search_chats_semantic",
                    "get_chat_summary",
                    "find_related_chats",
                    "filter_chats_by_date_range",
                ],
                "automation": [
                    "register_session_for_auto_save",
                    "trigger_auto_save_on_session_end",
                    "watch_chats_folder",
                    "import_chat_from_content",
                    "import_chat_from_local_path",
                    "sync_agent_transcripts",
                    "sync_cursor_agent_transcripts",
                ],
                "intelligence": [
                    "extract_action_items",
                    "build_knowledge_index",
                    "compare_two_chats",
                    "generate_project_brief_from_chats",
                ],
                "ops": [
                    "configure_connector_settings",
                    "compress_old_chat_archives",
                    "deduplicate_stored_chats",
                    "get_server_capabilities",
                ],
            },
            "client_paths": self.load_config().get("client_paths", {}),
            "total_tools": 25,
        }


_default_connector = ChatConnector()


def get_connector() -> ChatConnector:
    return _default_connector
