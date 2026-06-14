"""
Agent Workshop 核心（agent_core.py）— WG-12～21 邏輯 + WG-22 `Agent` 封裝。

對齊 `challenges-agent-workshop.md`（**WG-12～22**）；CLI 進入點見 **`main.py`**。
學生 CLI 進入點：**`main.py`**（`from agent_core import Agent`）。

公開 API：`Agent.create(workspace=..., session_name=...)`、`Agent.chat(user_text, *, image_path=..., on_token=...)`
"""

from __future__ import annotations

import base64
import copy
import json
import locale
import os
import platform
import re
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    message_chunk_to_message,
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from peas_agent.builtin_web import configure_web, web_fetch, web_search, web_tools_enabled
from peas_agent.prompt_templates import (
    load_bundled_template,
    render_template,
    sync_workspace_templates,
)
from peas_agent.memory_archive import archive_session_chunk
from peas_agent.memory_store import MemoryStore, configure_memory_store, get_memory_store
from peas_agent.tools_loader import (
    ToolsLoader,
    build_tools_summary,
    merge_tools,
)


BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md"]

PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path.home() / ".peas-agent"
CONFIG_PATH = DATA_DIR / "config.json"
DEFAULT_WORKSPACE = DATA_DIR / "workspace"
_ACTIVE_CONFIG: dict[str, Any] = {}
_RUNTIME_HOST_CONTEXT: str = ""
CONFIG_PATH_OVERRIDE: Path | None = None


def set_host_context(text: str | None) -> None:
    """Set optional host-environment overlay injected into build_system_prompt()."""
    global _RUNTIME_HOST_CONTEXT
    _RUNTIME_HOST_CONTEXT = (text or "").strip()


def _get_config_path() -> Path:
    if CONFIG_PATH_OVERRIDE is not None:
        return CONFIG_PATH_OVERRIDE
    return CONFIG_PATH


def _default_config() -> dict[str, Any]:
    return {
        "workspace": str(DEFAULT_WORKSPACE),
        "token_budget": 100000,
        "llm": {
            "api_key": "",
            "model": "gpt-5.4-mini",
            "temperature": 0.2,
            "base_url": "https://api.openai.com/v1",
        },
        "tools": {
            "web": {
                "enable": True,
                "proxy": None,
                "userAgent": None,
                "search": {
                    "provider": "duckduckgo",
                    "apiKey": "",
                    "maxResults": 5,
                    "timeout": 30,
                },
            },
        },
        "dream": {
            "enabled": True,
            "cron": "0 */2 * * *",
            "model": None,
            "max_batch_size": 20,
            "max_iterations": 10,
            "light_apply": True,
            "cross_session_archive": True,
            "cross_session_timing": "before_dream",
            "recent_history_max": 50,
            "summary_mode": "template",
        },
    }


def _ensure_config() -> dict[str, Any]:
    path = _get_config_path()
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        data = _default_config()
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"已建立設定檔 {path}；請編輯 llm.api_key 後重新執行。"
        )
        return data

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"警告：{path} 不是有效 JSON，使用內建預設值。")
        return _default_config()

    return loaded if isinstance(loaded, dict) else _default_config()


def _resolve_workspace(
    cli_workspace: str | Path | None,
    config: dict[str, Any],
) -> Path:
    if cli_workspace is not None:
        return Path(cli_workspace).expanduser().resolve()
    env_ws = os.environ.get("PEAS_AGENT_WORKSPACE")
    if env_ws:
        return Path(env_ws).expanduser().resolve()
    cfg_ws = config.get("workspace")
    if cfg_ws:
        return Path(str(cfg_ws)).expanduser().resolve()
    return DEFAULT_WORKSPACE.expanduser().resolve()


def init_workspace(workspace: Path) -> Path:
    root = workspace.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    sync_workspace_templates(root, silent=True)
    (root / "memory").mkdir(parents=True, exist_ok=True)
    (root / "sessions").mkdir(parents=True, exist_ok=True)
    (root / "skills").mkdir(parents=True, exist_ok=True)
    (root / "tools").mkdir(parents=True, exist_ok=True)
    return root


def _build_llm(config: dict[str, Any]) -> ChatOpenAI:
    llm_cfg = config.get("llm", {})
    if not isinstance(llm_cfg, dict):
        llm_cfg = {}
    api_key = (llm_cfg.get("api_key") or "").strip()
    if not api_key:
        raise RuntimeError(
            f"尚未設定 llm.api_key；請編輯 {_get_config_path()}。"
        )
    kwargs: dict[str, Any] = {
        "api_key": api_key,
        "model": llm_cfg.get("model", "gpt-5.4-mini"),
        "temperature": llm_cfg.get("temperature", 0.2),
    }
    base_url = (llm_cfg.get("base_url") or "").strip()
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def _validate_session_name(session_name: str) -> str:
    name = session_name.strip()
    if not name:
        raise ValueError("session_name 不可為空")
    if name != Path(name).name or ".." in name or "/" in name or "\\" in name:
        raise ValueError(f"無效的 session 檔名：{session_name!r}")
    if not name.endswith(".jsonl"):
        name = f"{name}.jsonl"
    return name


def _ensure_session_dir(workspace: Path) -> Path:
    session_dir = workspace / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def _new_session_path(session_dir: Path) -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shortid = uuid.uuid4().hex[:6]
    path = session_dir / f"session_{stamp}_{shortid}.jsonl"
    path.touch(exist_ok=False)
    return path


DEFAULT_SESSION_NAME = "session.jsonl"


def _resolve_session_path(
    workspace: Path,
    session_name: str | None,
) -> Path:
    session_dir = _ensure_session_dir(workspace)
    if session_name is None:
        return session_dir / DEFAULT_SESSION_NAME
    safe_name = _validate_session_name(session_name)
    return session_dir / safe_name


def _set_memory_paths(workspace: Path) -> None:
    global MEMORY_DIR, MEMORY_PATH, HISTORY_PATH
    MEMORY_DIR = workspace / "memory"
    MEMORY_PATH = MEMORY_DIR / "MEMORY.md"
    HISTORY_PATH = MEMORY_DIR / "HISTORY.md"


def _configure_runtime(workspace: Path, config: dict[str, Any]) -> MemoryStore:
    global WORKSPACE, SKILLS_LOADER, TOOLS_LOADER, _ACTIVE_CONFIG
    WORKSPACE = workspace
    _ACTIVE_CONFIG = config
    configure_web(config)
    _set_memory_paths(workspace)
    SKILLS_LOADER = SkillsLoader(
        workspace,
        builtin_dir=PACKAGE_DIR / "builtin_skills",
    )
    TOOLS_LOADER = ToolsLoader(workspace)
    return configure_memory_store(workspace)


# ---------------------------------------------------------------------------
# WG-12：人設與 system／history 分離（main 內 system_text；不寫 SystemMessage 進 JSONL）
# ---------------------------------------------------------------------------
# 每輪以 build_system_prompt() 產生 system_text；完整實作見 WG-20。


# ---------------------------------------------------------------------------
# WG-13：identity／bootstrap、add_numbers、串流輔助（run_react_turn 見 WG-18 之後）
# ---------------------------------------------------------------------------


def _detect_shell_name() -> str:
    shell = os.environ.get("SHELL") or os.environ.get("COMSPEC") or ""
    shell_name = Path(shell).name if shell else ""
    if os.name == "nt":
        if "powershell" in shell_name.lower() or os.environ.get("PSModulePath"):
            return "PowerShell"
        return shell_name or "Windows shell"
    return shell_name or "POSIX shell"


def _get_identity(workspace: Path) -> str:
    """Render identity + platform policy from bundled templates."""
    root = workspace.expanduser().resolve()
    system = platform.system()
    runtime = (
        f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, "
        f"Python {platform.python_version()}"
    )
    platform_policy = render_template(
        "agent/platform_policy.md",
        system=system,
        shell_name=_detect_shell_name(),
    )
    return render_template(
        "agent/identity.md",
        workspace_path=str(root),
        runtime=runtime,
        platform_policy=platform_policy,
    )


def _load_bootstrap_files(workspace: Path) -> str:
    """Load workspace bootstrap files (AGENTS.md, SOUL.md, USER.md)."""
    parts: list[str] = []
    root = workspace.expanduser().resolve()
    for filename in BOOTSTRAP_FILES:
        file_path = root / filename
        if file_path.is_file():
            content = file_path.read_text(encoding="utf-8")
            parts.append(f"## {filename}\n\n{content}")
    return "\n\n".join(parts) if parts else ""


@tool
def add_numbers(a: float, b: float) -> float:
    """兩個數字相加並回傳和。純算術必須呼叫此工具，不可心算後直接回答。"""
    return float(a) + float(b)


def _stream_model_response(
    llm_tools: ChatOpenAI,
    messages: list[BaseMessage],
    on_token: Callable[[str], None] | None = None,
) -> AIMessage:
    """串流累積為 AIMessage；僅印模型文字，工具執行由呼叫端處理。"""
    acc: AIMessageChunk | None = None
    for chunk in llm_tools.stream(messages):
        acc = chunk if acc is None else acc + chunk
        content = chunk.content
        if isinstance(content, str) and content:
            if on_token is not None:
                on_token(content)
            else:
                print(content, end="", flush=True)
    if acc is None:
        raise RuntimeError("模型串流未回傳任何 chunk")
    return message_chunk_to_message(acc)


# ---------------------------------------------------------------------------
# WG-14：workspace 檔案／shell `@tool`（追加至 WG-13 之 TOOLS）
# ---------------------------------------------------------------------------

WORKSPACE = DEFAULT_WORKSPACE.expanduser().resolve()


def resolve_workspace_path(path: str) -> Path:
    """Resolve a filesystem path. Absolute paths are used as-is; relative paths are under WORKSPACE."""
    raw = Path(path)
    if raw.is_absolute():
        return raw.expanduser().resolve()
    return (WORKSPACE / path).expanduser().resolve()


def _resolve_readable_path(path: str) -> Path:
    """Resolve a readable file path, with package builtin_skills/ as a relative-path fallback."""
    target = resolve_workspace_path(path)
    if target.is_file():
        return target

    if not Path(path).is_absolute():
        pkg_target = (PACKAGE_DIR / path).expanduser().resolve()
        if pkg_target.is_file():
            return pkg_target
    return target


@tool("read_file")
def read_file(path: str, offset: int = 1, limit: int = 200) -> str:
    """讀取 UTF-8 文字檔，回傳帶行號內容。接受絕對路徑或相對於 workspace 的路徑。"""
    try:
        target = _resolve_readable_path(path)
        if not target.is_file():
            return f"Error: not a file: {path}"
        lines = target.read_text(encoding="utf-8").splitlines()
        start = max(offset - 1, 0)
        end = min(start + limit, len(lines))
        return "\n".join(f"{i + 1}| {line}" for i, line in enumerate(lines[start:end], start))
    except Exception as e:
        return f"Error: {e}"


@tool("write_file")
def write_file(path: str, content: str) -> str:
    """整檔覆寫寫入 UTF-8 文字檔（必要時建立父資料夾）。接受絕對路徑或相對於 workspace 的路徑。"""
    try:
        target = resolve_workspace_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error: {e}"


@tool("edit_file")
def edit_file(path: str, old_text: str, new_text: str, replace_all: bool = False) -> str:
    """在既有檔案中把 old_text 換成 new_text（預設僅單次替換）。接受絕對路徑或相對於 workspace 的路徑。"""
    try:
        target = resolve_workspace_path(path)
        text = target.read_text(encoding="utf-8")
        count = text.count(old_text)
        if count == 0:
            return "Error: old_text not found"
        if count > 1 and not replace_all:
            return "Error: old_text appears multiple times"
        target.write_text(
            text.replace(old_text, new_text, -1 if replace_all else 1),
            encoding="utf-8",
        )
        return f"edited {path}"
    except Exception as e:
        return f"Error: {e}"


@tool("list_dir")
def list_dir(path: str, recursive: bool = False, max_entries: int = 200) -> str:
    """列出資料夾內容。接受絕對路徑或相對於 workspace 的路徑。"""
    try:
        root = resolve_workspace_path(path)
        if not root.is_dir():
            return f"Error: not a directory: {path}"
        iterator = root.rglob("*") if recursive else root.iterdir()
        entries = [str(item) for item in iterator][:max_entries]
        return "\n".join(entries) if entries else "(empty)"
    except Exception as e:
        return f"Error: {e}"


@tool("exec")
def exec_workspace(command: str, timeout: int = 30, cwd: str | None = None) -> str:
    """執行 shell 指令（已阻擋常見危險片段）。可選 cwd 指定工作目錄；預設為 workspace。"""
    blocked = ("rm -rf", "del /f", "rmdir /s", "format", "shutdown")
    lowered = command.lower()
    if any(part in lowered for part in blocked):
        return "Error: blocked dangerous command (safety limit)"
    if os.name == "nt" and "<<" in command:
        return (
            "Error: heredoc syntax is disabled in this Windows runtime. "
            "Use write_file to create a .py script, then run it with "
            "uv run python <script.py>."
        )

    work_dir = resolve_workspace_path(cwd) if cwd else WORKSPACE
    if not work_dir.is_dir():
        return f"Error: not a directory: {cwd or WORKSPACE}"

    child_env = os.environ.copy()
    child_env.setdefault("PYTHONUTF8", "1")
    child_env.setdefault("PYTHONIOENCODING", "utf-8")

    run_kw: dict[str, Any] = {
        "cwd": str(work_dir),
        "shell": True,
        "capture_output": True,
        "timeout": timeout,
        "env": child_env,
    }
    if os.name == "nt":
        run_kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        result = subprocess.run(command, **run_kw)
        stdout = _decode_process_output(result.stdout or b"")
        stderr = _decode_process_output(result.stderr or b"")
        output = (stdout + stderr).strip()
        cap = 4000
        if len(output) > cap:
            output = output[:cap] + "\n\n[truncated]"
        if not output:
            output = "(no stdout or stderr; command finished with no captured output)"
        return f"exit_code={result.returncode}\n{output}"
    except Exception as e:
        return f"Error: {e}"


def _get_builtin_tools() -> list[Any]:
    tools: list[Any] = [
        add_numbers,
        read_file,
        write_file,
        edit_file,
        list_dir,
        exec_workspace,
    ]
    if web_tools_enabled():
        tools.extend([web_search, web_fetch])
    return tools


def _decode_process_output(data: bytes) -> str:
    encodings = ["utf-8", locale.getpreferredencoding(False), "cp950"]
    for encoding in dict.fromkeys(encodings):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


BUILTIN_TOOLS = _get_builtin_tools()

_TOOL_BY_NAME: dict[str, Any] = {t.name: t for t in BUILTIN_TOOLS}


def _rebuild_tool_registry(all_tools: list[Any]) -> None:
    global _TOOL_BY_NAME
    _TOOL_BY_NAME = {t.name: t for t in all_tools}


def _load_all_tools() -> list[Any]:
    result = _tools_loader().load_all()
    warnings = list(result.warnings)
    merged = merge_tools(_get_builtin_tools(), result.tools, warnings=warnings)
    for warning in warnings:
        print(f"（tools: {warning}）")
    _rebuild_tool_registry(merged)
    return merged


def _run_bound_tool(name: str, args: dict[str, Any]) -> str:
    tool_obj = _TOOL_BY_NAME.get(name)
    if tool_obj is None:
        return f"Error: unknown tool {name!r}"
    try:
        out = tool_obj.invoke(dict(args or {}))
        return str(out)
    except Exception as e:
        return f"Error running tool {name}: {e}"


# ---------------------------------------------------------------------------
# WG-15：JSONL 寫入（每輪 extend 後 save；第一行 metadata；不寫 SystemMessage）
# ---------------------------------------------------------------------------


def _default_metadata(created_at: str | None = None) -> dict[str, Any]:
    """建立第一行 metadata 物件（與 session.jsonl.example 欄位對齊）。"""
    now = datetime.now().isoformat()
    return {
        "_type": "metadata",
        "key": "session",
        "created_at": created_at or now,
        "updated_at": now,
        "metadata": {},
        "last_consolidated": 0,
    }


def _serialize_tool_calls(tc: Any) -> list[dict[str, Any]]:
    if not tc:
        return []
    out: list[dict[str, Any]] = []
    for item in tc:
        if isinstance(item, dict):
            out.append(
                {
                    "name": item.get("name", ""),
                    "args": dict(item.get("args") or {}),
                    "id": str(item.get("id", "")),
                }
            )
    return out


def _message_to_jsonl_line(m: BaseMessage) -> str | None:
    ts = datetime.now().isoformat()
    if isinstance(m, HumanMessage):
        text, image_path, media_type = human_fields_for_jsonl(m)
        row: dict[str, Any] = {"role": "user", "content": text, "timestamp": ts}
        if image_path:
            row["image_path"] = image_path
            if media_type:
                row["media_type"] = media_type
    elif isinstance(m, AIMessage):
        row = {"role": "assistant", "content": m.content, "timestamp": ts}
        tc = getattr(m, "tool_calls", None)
        if tc:
            row["tool_calls"] = _serialize_tool_calls(tc)
    elif isinstance(m, ToolMessage):
        row = {
            "role": "tool",
            "content": m.content,
            "tool_call_id": m.tool_call_id,
            "timestamp": ts,
        }
        tname = getattr(m, "name", None)
        if tname:
            row["name"] = tname
    else:
        return None
    return json.dumps(row, ensure_ascii=False)


def save_session_jsonl(
    path: str,
    messages: list[BaseMessage],
    existing_meta: dict[str, Any] | None,
    last_consolidated: int,
) -> dict[str, Any]:
    now = datetime.now().isoformat()
    if existing_meta is None:
        meta = _default_metadata(created_at=now)
    else:
        meta = dict(existing_meta)
        meta["_type"] = "metadata"
        meta["key"] = meta.get("key", "session")
        if "created_at" not in meta:
            meta["created_at"] = now
        meta["updated_at"] = now
    meta["last_consolidated"] = last_consolidated

    lines: list[str] = [json.dumps(meta, ensure_ascii=False)]
    for m in messages:
        line = _message_to_jsonl_line(m)
        if line is not None:
            lines.append(line)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        if lines:
            f.write("\n")

    return meta


# ---------------------------------------------------------------------------
# WG-16：JSONL 載入（啟動還原 history／session_meta；壞行略過）
# ---------------------------------------------------------------------------


def _row_to_message(obj: dict[str, Any]) -> BaseMessage | None:
    role = obj.get("role")
    if role == "user":
        return load_user_row_to_history_human(obj)
    if role == "assistant":
        content = str(obj.get("content", ""))
        tc = obj.get("tool_calls")
        if tc:
            return AIMessage(content=content, tool_calls=_serialize_tool_calls(tc))
        return AIMessage(content=content)
    if role == "tool":
        tid = obj.get("tool_call_id") or ""
        nm = str(obj.get("name", "") or "").strip() or None
        return ToolMessage(
            content=str(obj.get("content", "")),
            tool_call_id=str(tid),
            name=nm,
        )
    return None


def load_session_jsonl(path: str) -> tuple[list[BaseMessage], dict[str, Any] | None]:
    if not os.path.exists(path):
        return [], None

    messages: list[BaseMessage] = []
    meta: dict[str, Any] | None = None

    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj: Any = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(obj, dict) and obj.get("_type") == "metadata":
                meta = obj
                continue

            if isinstance(obj, dict):
                msg = _row_to_message(obj)
                if msg is not None:
                    messages.append(msg)

    return messages, meta


# ---------------------------------------------------------------------------
# WG-21：多模態附圖、JSONL image_path、history 占位、送模剝歷史圖
# ---------------------------------------------------------------------------

_IMAGE_PLACEHOLDER_RE = re.compile(
    r"\n\n\[此回合曾附圖，路徑：([^\]]+)\](?:（media_type=([^）]+)）)?\s*$"
)


def guess_media_type(path: Path, fallback: str = "image/png") -> str:
    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    return fallback


def image_bytes_to_data_url(data: bytes, media_type: str) -> str:
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{media_type};base64,{b64}"


def resolve_project_image_path(rel: str) -> Path:
    """WG-21：解析附圖路徑。絕對路徑直接使用；相對路徑以 workspace（或 cwd）為基準。"""
    raw = Path(rel)
    if raw.is_absolute():
        return raw.expanduser().resolve()
    base = WORKSPACE if WORKSPACE is not None else Path.cwd()
    return (base / rel).expanduser().resolve()


def parse_history_human_content(content: str) -> tuple[str, str | None, str | None]:
    match = _IMAGE_PLACEHOLDER_RE.search(content)
    if not match:
        return content, None, None
    text = content[: match.start()].rstrip()
    return text, match.group(1), match.group(2)


def history_human_placeholder(
    text: str, image_rel: str | None, media_type: str | None = None
) -> HumanMessage:
    """WG-21：寫入 history／JSONL 前之純字串 user（含附圖占位）。"""
    if not image_rel:
        return HumanMessage(content=text)
    extra = f"[此回合曾附圖，路徑：{image_rel}]"
    if media_type:
        extra += f"（media_type={media_type}）"
    body = f"{text}\n\n{extra}" if text else extra
    return HumanMessage(content=body)


def human_fields_for_jsonl(m: HumanMessage) -> tuple[str, str | None, str | None]:
    """自 history 占位 HumanMessage 抽出 JSONL 欄位（不得序列化 list content）。"""
    if isinstance(m.content, list):
        raise ValueError("WG-21：不可將多模態 HumanMessage 直接寫入 JSONL")
    content = str(m.content)
    text, image_path, media_type = parse_history_human_content(content)
    return text, image_path, media_type


def load_user_row_to_history_human(row: dict[str, Any]) -> HumanMessage:
    """WG-21／WG-16：冷啟動載入 user 列；有 image_path 亦只還原占位，不讀圖。"""
    text = str(row.get("content", ""))
    rel = row.get("image_path")
    if not rel:
        return HumanMessage(content=text)
    mt = row.get("media_type")
    return history_human_placeholder(text, str(rel), str(mt) if mt else None)


def build_human_message_for_current_turn(
    text: str, image_rel: str | None
) -> HumanMessage:
    """WG-21：僅本輪送模可組多模態；此時才 open(rb)。"""
    if not image_rel:
        return HumanMessage(content=text)

    try:
        full = resolve_project_image_path(image_rel)
    except PermissionError as e:
        print(f"[warn] rejected image path: {e}")
        return HumanMessage(content=text)

    if not full.is_file():
        print(f"[warn] missing image for current turn: {image_rel}")
        return HumanMessage(content=text)

    media_type = guess_media_type(full)
    with open(full, "rb") as f:
        data = f.read()
    url = image_bytes_to_data_url(data, media_type)
    blocks: list[dict[str, Any]] = []
    if text:
        blocks.append({"type": "text", "text": text})
    blocks.append({"type": "image_url", "image_url": {"url": url}})
    return HumanMessage(content=blocks)


def _human_text_length(message: HumanMessage) -> int:
    content = message.content
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                total += len(str(block.get("text", "")))
        return total
    return len(str(content))


def _human_to_text_only_for_model(m: HumanMessage) -> HumanMessage:
    """WG-21：送模前剝除 history 內 image_url 區塊。"""
    content = m.content
    if isinstance(content, str):
        return copy.deepcopy(m)
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        body = (
            "\n".join(p for p in parts if p).strip()
            or "[（無文字）此則曾含圖，已於送模層剝除圖區塊]"
        )
        return HumanMessage(content=body + "\n\n[送模層已剝除歷史圖區塊]")
    return HumanMessage(content=str(content))


def _last_human_index(messages: list[BaseMessage]) -> int | None:
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            return i
    return None


def _keep_image_only_on_current_human(messages: list[BaseMessage]) -> list[BaseMessage]:
    """WG-21：送模副本中，僅本輪（最後一則）HumanMessage 可保留 image；其餘剝為純文字。"""
    last_human = _last_human_index(messages)
    out: list[BaseMessage] = []
    for i, msg in enumerate(messages):
        mm = copy.deepcopy(msg)
        if isinstance(mm, HumanMessage) and last_human is not None and i != last_human:
            mm = _human_to_text_only_for_model(mm)
        out.append(mm)
    return out


# ---------------------------------------------------------------------------
# WG-17：字元預算與送模裁切（history 全量保留，past 為送模切片）
# ---------------------------------------------------------------------------


def get_token_budget() -> int:
    raw = _ACTIVE_CONFIG.get("token_budget", 100000)
    try:
        n = int(raw)
        return n if n > 0 else 100000
    except (TypeError, ValueError):
        return 100000


def estimate_message_tokens(message: BaseMessage) -> int:
    if isinstance(message, HumanMessage):
        return _human_text_length(message)
    content = message.content
    return len(content) if isinstance(content, str) else 0


def message_cost(msgs: list[BaseMessage]) -> int:
    return sum(estimate_message_tokens(m) for m in msgs)


def pick_consolidation_boundary(
    messages: list[BaseMessage],
    last_consolidated: int,
    tokens_to_remove: int,
) -> tuple[int, int] | None:
    """自 last_consolidated 掃描，挑「使用者回合開頭」idx，使略過的權重足夠。"""
    start = last_consolidated
    if start >= len(messages) or tokens_to_remove <= 0:
        return None

    removed_tokens = 0
    last_boundary: tuple[int, int] | None = None
    for idx in range(start, len(messages)):
        message = messages[idx]
        if idx > start and isinstance(message, HumanMessage):
            last_boundary = (idx, removed_tokens)
            if removed_tokens >= tokens_to_remove:
                return last_boundary
        removed_tokens += estimate_message_tokens(message)

    return last_boundary


# ---------------------------------------------------------------------------
# WG-18：送模 transcript 修復（完整 history 與 messages_for_model 副本分離）
# ---------------------------------------------------------------------------


def _known_tool_call_ids(messages: list[BaseMessage], before_index: int) -> set[str]:
    ids: set[str] = set()
    for msg in messages[:before_index]:
        if not isinstance(msg, AIMessage):
            continue
        for tc in msg.tool_calls or []:
            if isinstance(tc, dict):
                tid = tc.get("id")
                if tid:
                    ids.add(str(tid))
    return ids


def messages_for_model(messages: list[BaseMessage]) -> list[BaseMessage]:
    """WG-18＋WG-21：送模副本（tool 修復；歷史剝圖、本輪可多模態）。

    回傳新 list，不就地修改輸入（避免污染將寫入 JSONL 的 history）。
    """
    out: list[BaseMessage] = copy.deepcopy(messages)

    # A: drop orphan ToolMessage rows
    kept: list[BaseMessage] = []
    for msg in out:
        if isinstance(msg, ToolMessage):
            tid = str(msg.tool_call_id or "")
            if tid and tid in _known_tool_call_ids(kept, len(kept)):
                kept.append(msg)
        else:
            kept.append(msg)
    out = kept

    # B: backfill missing ToolMessage after AIMessage tool_calls
    unavailable_tool_text = "[Tool result unavailable — call was interrupted or lost]"
    i = 0
    while i < len(out):
        msg = out[i]
        if not isinstance(msg, AIMessage):
            i += 1
            continue
        tool_calls = msg.tool_calls or []
        if not tool_calls:
            i += 1
            continue

        j = i + 1
        responded: set[str] = set()
        while j < len(out) and isinstance(out[j], ToolMessage):
            responded.add(str(out[j].tool_call_id or ""))
            j += 1

        insert_at = j
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            tid = str(tc.get("id", "") or "")
            if not tid or tid in responded:
                continue
            name = str(tc.get("name", "") or "").strip() or None
            out.insert(
                insert_at,
                ToolMessage(
                    content=unavailable_tool_text,
                    tool_call_id=tid,
                    name=name,
                ),
            )
            insert_at += 1
        i += 1

    return _keep_image_only_on_current_human(out)


# ---------------------------------------------------------------------------
# WG-13（續）：run_react_turn（依 WG-14 _TOOL_BY_NAME、WG-18 messages_for_model）
# ---------------------------------------------------------------------------


def run_react_turn(
    llm_tools: ChatOpenAI,
    system_text: str,
    past: list[BaseMessage],
    human_message: HumanMessage,
    history_human: HumanMessage | None = None,
    on_token: Callable[[str], None] | None = None,
) -> tuple[str, list[BaseMessage]]:
    """單輪 ReAct：stream → tool_calls → ToolMessage 迴圈，直到純文字回覆。

    WG-17：`past` 為裁切後送模切片；完整 `history` 由 `main()` 另行累積。
    WG-18＋WG-21：每段 stream 前以 `messages_for_model` 修復 transcript 並剝歷史圖。
    WG-21：`human_message` 可為本輪多模態；`history_human` 為寫入 history 之占位版。
    """
    messages: list[BaseMessage] = [
        SystemMessage(content=system_text),
        *past,
        human_message,
    ]
    idx_turn_start = 1 + len(past)

    while True:
        messages = messages_for_model(messages)
        response = _stream_model_response(llm_tools, messages, on_token=on_token)
        messages.append(response)
        print()

        if response.tool_calls:
            for tc in response.tool_calls:
                name = str(tc["name"])
                raw_args = dict(tc.get("args") or {})
                result = _run_bound_tool(name, raw_args)
                print(f"\n[工具 {name}]\n{result}\n", flush=True)
                messages.append(
                    ToolMessage(
                        content=result,
                        tool_call_id=str(tc["id"]),
                        name=name,
                    )
                )
        else:
            break

    turn_messages = messages[idx_turn_start:]
    if history_human is not None and turn_messages:
        turn_messages = [history_human, *turn_messages[1:]]
    final_content = response.content
    final_text = (
        final_content.strip()
        if isinstance(final_content, str)
        else str(final_content).strip()
    )
    return final_text, turn_messages


def run_dream_react_turn(
    llm_tools: ChatOpenAI,
    system_text: str,
    user_text: str,
    *,
    max_iterations: int = 10,
    tool_runner: Callable[[str, dict[str, Any]], str] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """Dream Phase 2 ReAct with iteration cap; tool errors do not abort."""

    def _invoke_tool(name: str, args: dict[str, Any]) -> str:
        if tool_runner is not None:
            return tool_runner(name, args)
        return _run_bound_tool(name, args)

    messages: list[BaseMessage] = [
        SystemMessage(content=system_text),
        HumanMessage(content=user_text),
    ]
    tool_events: list[dict[str, str]] = []
    final_text = ""

    for _ in range(max_iterations):
        response = llm_tools.invoke(messages)
        messages.append(response)

        if not getattr(response, "tool_calls", None):
            content = response.content
            final_text = content.strip() if isinstance(content, str) else str(content).strip()
            break

        for tc in response.tool_calls:
            name = str(tc["name"])
            raw_args = dict(tc.get("args") or {})
            result = _invoke_tool(name, raw_args)
            status = "ok" if not str(result).startswith("Error") else "error"
            tool_events.append({"name": name, "status": status, "detail": result[:200]})
            messages.append(
                ToolMessage(
                    content=result,
                    tool_call_id=str(tc["id"]),
                    name=name,
                )
            )
    else:
        final_text = "[dream phase2: max iterations reached]"

    return final_text, tool_events


# ---------------------------------------------------------------------------
# WG-19：長期記憶（history.jsonl 歸檔 + Dream 合成 MEMORY/SOUL/USER）
# ensure_budget_before_react 見 WG-20 之後（呼叫 build_system_prompt）
# ---------------------------------------------------------------------------

REFERENCE_DIR = PACKAGE_DIR
MEMORY_DIR = DEFAULT_WORKSPACE / "memory"
MEMORY_PATH = MEMORY_DIR / "MEMORY.md"
HISTORY_PATH = MEMORY_DIR / "HISTORY.md"
MEMORY_TEMPLATE_PATH = PACKAGE_DIR / "templates" / "memory" / "MEMORY.md"
MEMORY_MERGE_PROMPT_PATH = PACKAGE_DIR / "prompts" / "memory_merge.md"
LONG_TERM_MEMORY_HEADING = "## Long-term Memory"
CONSOLIDATION_MAX_RETRIES = 3


def read_memory_md(store: MemoryStore | None = None) -> str:
    try:
        memory_store = store if store is not None else get_memory_store()
        return memory_store.read_memory().strip()
    except RuntimeError:
        if not MEMORY_PATH.is_file():
            return ""
        return MEMORY_PATH.read_text(encoding="utf-8").strip()


def load_memory_merge_prompt() -> str:
    return MEMORY_MERGE_PROMPT_PATH.read_text(encoding="utf-8")


def is_default_memory_template(content: str) -> bool:
    """True when MEMORY.md is still the bundled nanobot starter template."""
    if not content.strip():
        return True
    if not MEMORY_TEMPLATE_PATH.is_file():
        return False
    return content.strip() == MEMORY_TEMPLATE_PATH.read_text(encoding="utf-8").strip()


def memory_block_for_system(store: MemoryStore | None = None) -> str:
    """有 MEMORY.md 內文且非預設模板時，回傳 ## Long-term Memory 區塊（全文讀入，不截斷）。"""
    body = read_memory_md(store)
    if not body or is_default_memory_template(body):
        return ""
    return f"{LONG_TERM_MEMORY_HEADING}\n\n{body}"


def append_history_log(line: str) -> None:
    """Deprecated: use MemoryStore.append_history via archive flow."""
    try:
        store = get_memory_store()
        store.append_history(" ".join(line.split()))
    except RuntimeError:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        single = " ".join(line.split())
        with open(HISTORY_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {single}\n")


def write_memory_md(content: str) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(content, encoding="utf-8")


def _message_plaintext(message: BaseMessage) -> str:
    if isinstance(message, HumanMessage):
        role = "user"
    elif isinstance(message, AIMessage):
        role = "assistant"
    elif isinstance(message, ToolMessage):
        role = "tool"
    else:
        role = "other"
    if isinstance(message, HumanMessage):
        content = (
            message.content
            if isinstance(message.content, str)
            else _human_to_text_only_for_model(message).content
        )
    else:
        content = message.content if isinstance(message.content, str) else str(message.content)
    extra = ""
    if isinstance(message, AIMessage) and message.tool_calls:
        names = [
            str(tc.get("name", ""))
            for tc in message.tool_calls
            if isinstance(tc, dict)
        ]
        extra = f" [tool_calls: {', '.join(names)}]"
    return f"{role}{extra}: {content}"


def _chunk_to_text(chunk: list[BaseMessage]) -> str:
    return "\n".join(_message_plaintext(m) for m in chunk)


def _parse_consolidation_json(text: str) -> dict[str, str] | None:
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "history_entry" in obj and "memory_update" in obj:
            return {
                "history_entry": str(obj["history_entry"]),
                "memory_update": str(obj["memory_update"]),
            }
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            if isinstance(obj, dict) and "history_entry" in obj and "memory_update" in obj:
                return {
                    "history_entry": str(obj["history_entry"]),
                    "memory_update": str(obj["memory_update"]),
                }
        except json.JSONDecodeError:
            pass
    return None


def _invoke_consolidation(
    consolidation_llm: ChatOpenAI,
    chunk_text: str,
    existing_memory: str,
) -> dict[str, str] | None:
    consolidation_system = load_memory_merge_prompt()
    user_prompt = (
        f"## CURRENT MEMORY\n{existing_memory or '（空）'}\n\n"
        f"## CONVERSATION CHUNK\n{chunk_text}\n\n"
        "僅回傳 JSON，不要其他文字。"
    )
    response = consolidation_llm.invoke(
        [
            SystemMessage(content=consolidation_system),
            HumanMessage(content=user_prompt),
        ]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)
    return _parse_consolidation_json(content)


def _consolidate_pack(
    consolidation_llm: ChatOpenAI,
    chunk: list[BaseMessage],
    session_key: str,
    store: MemoryStore,
) -> None:
    """Archive chunk summary to history.jsonl (Dream updates MEMORY later)."""
    if not chunk:
        return
    archive_session_chunk(
        consolidation_llm,
        store,
        chunk,
        session_key,
        message_plaintext=_message_plaintext,
    )


# ---------------------------------------------------------------------------
# WG-20：SkillsLoader、build_system_prompt（送模唯一入口）
# ---------------------------------------------------------------------------


@dataclass
class SkillEntry:
    name: str
    path: str
    source: str
    description: str
    always: bool
    body: str


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text

    lines = text.splitlines()
    end: int | None = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return {}, text

    meta: dict[str, str] = {}
    for raw in lines[1:end]:
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        meta[key.strip()] = value.strip()

    body = "\n".join(lines[end + 1 :]).strip()
    return meta, body


class SkillsLoader:
    def __init__(
        self,
        workspace: Path,
        *,
        builtin_dir: Path | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.workspace_skills = self.workspace / "skills"
        self.builtin_skills = (builtin_dir or PACKAGE_DIR / "builtin_skills").resolve()

    def _skill_path_for_read(self, skill_file: Path) -> str:
        resolved = skill_file.resolve()
        try:
            return resolved.relative_to(self.workspace).as_posix()
        except ValueError:
            return resolved.relative_to(self.builtin_skills.parent).as_posix()

    def _entries_from_dir(
        self, root: Path, source: str, skip: set[str]
    ) -> list[SkillEntry]:
        if not root.exists():
            return []

        entries: list[SkillEntry] = []
        for skill_dir in sorted(root.iterdir(), key=lambda p: p.name):
            skill_file = skill_dir / "SKILL.md"
            if not skill_dir.is_dir() or not skill_file.is_file():
                continue
            if skill_dir.name in skip:
                continue

            text = skill_file.read_text(encoding="utf-8")
            meta, body = split_frontmatter(text)
            name = skill_dir.name
            description = meta.get("description") or name
            always = meta.get("always", "false").lower() == "true"
            rel_path = self._skill_path_for_read(skill_file)
            entries.append(
                SkillEntry(name, rel_path, source, description, always, body)
            )
        return entries

    def list_skills(self) -> list[SkillEntry]:
        workspace_entries = self._entries_from_dir(
            self.workspace_skills, "workspace", set()
        )
        workspace_names = {entry.name for entry in workspace_entries}
        builtin_entries = self._entries_from_dir(
            self.builtin_skills, "builtin", workspace_names
        )
        return workspace_entries + builtin_entries

    def load_skill(self, name: str) -> str | None:
        for root in (self.workspace_skills, self.builtin_skills):
            path = root / name / "SKILL.md"
            if path.is_file():
                return path.read_text(encoding="utf-8")
        return None


def build_skills_summary(entries: list[SkillEntry]) -> str:
    summarized = [e for e in entries if not e.always]
    if not summarized:
        return ""
    lines = [f"- **{e.name}** — {e.description} `{e.path}`" for e in summarized]
    return "\n".join(lines)


SKILLS_LOADER: SkillsLoader | None = None
TOOLS_LOADER: ToolsLoader | None = None

_RUNTIME_NOT_CONFIGURED = "Agent runtime not configured; call Agent.create() first."


def _skills_loader() -> SkillsLoader:
    if SKILLS_LOADER is None:
        raise RuntimeError(_RUNTIME_NOT_CONFIGURED)
    return SKILLS_LOADER


def _tools_loader() -> ToolsLoader:
    if TOOLS_LOADER is None:
        raise RuntimeError(_RUNTIME_NOT_CONFIGURED)
    return TOOLS_LOADER


def build_system_prompt(store: MemoryStore | None = None) -> str:
    """WG-12～20 送模 system 唯一入口（identity + bootstrap + tool_contract + memory + Skills）。"""
    parts: list[str] = [_get_identity(WORKSPACE)]

    bootstrap = _load_bootstrap_files(WORKSPACE)
    if bootstrap:
        parts.append(bootstrap)

    if _RUNTIME_HOST_CONTEXT:
        parts.append(f"# Host Environment\n\n{_RUNTIME_HOST_CONTEXT}")

    parts.append(render_template("agent/tool_contract.md"))

    mem = memory_block_for_system(store)
    if mem:
        parts.append(mem)

    memory_store = store
    if memory_store is None:
        try:
            memory_store = get_memory_store(WORKSPACE)
        except RuntimeError:
            memory_store = None
    if memory_store is not None:
        dream_cfg = _ACTIVE_CONFIG.get("dream", {})
        if not isinstance(dream_cfg, dict):
            dream_cfg = {}
        max_recent = int(dream_cfg.get("recent_history_max", 50))
        if max_recent > 0:
            entries = memory_store.read_unprocessed_history(
                since_cursor=memory_store.get_last_dream_cursor()
            )
            if entries:
                capped = entries[-max_recent:]
                lines = [
                    f"- [{e.get('timestamp', '?')}] {e.get('content', '')}"
                    for e in capped
                ]
                parts.append("# Recent History\n\n" + "\n".join(lines))

    entries = _skills_loader().list_skills()
    active = [e for e in entries if e.always]
    if active:
        body = "\n\n---\n\n".join(
            f"### Skill: {e.name}\n\n{e.body}" for e in active
        )
        parts.append(f"# Active Skills\n\n{body}")

    summary = build_skills_summary(entries)
    if summary:
        intro = (
            "下列技能可擴充你的能力。若要使用某技能，請用 read_file 讀取清單中"
            "該技能路徑下的 SKILL.md。\n"
            "若該技能需額外套件或環境，請先依 SKILL.md 或專案說明安裝相依項目後再操作。\n\n"
        )
        parts.append("# Skills\n\n" + intro + summary)

    tool_entries = _tools_loader().list_entries()
    tools_summary = build_tools_summary(tool_entries)
    if tools_summary:
        tool_intro = (
            "下列為使用者自訂工具，已透過 function calling 綁定，可直接呼叫。\n"
            "修改 tools/ 下的檔案後需重啟 agent 才會重新載入。\n\n"
        )
        parts.append("# Custom Tools\n\n" + tool_intro + tools_summary)

    return "\n\n---\n\n".join(parts) if len(parts) > 1 else parts[0]


# ---------------------------------------------------------------------------
# WG-19（續）：ensure_budget_before_react（ReAct 前；依 WG-17、WG-20 build_system_prompt）
# ---------------------------------------------------------------------------


def ensure_budget_before_react(
    consolidation_llm: ChatOpenAI,
    history: list[BaseMessage],
    last_consolidated: int,
    human_message: HumanMessage,
    store: MemoryStore,
    *,
    session_key: str = "session.jsonl",
) -> int:
    """WG-19：ReAct 前外層迴圈 — Phase A 規劃 final_idx，Phase B 整包整併 + 推游標。

    僅在 cost <= get_token_budget() // 2 時 return；呼叫端可直接進入 ReAct，無需再驗證。
    """
    target = get_token_budget() // 2

    while True:
        # Phase A — 規劃（不呼叫 consolidation LLM）
        system_text = build_system_prompt(store)
        past0 = history[last_consolidated:]
        cost = len(system_text) + message_cost([*past0, human_message])
        if cost <= target:
            return last_consolidated

        tokens_to_remove = max(0, cost - target)
        boundary = pick_consolidation_boundary(
            history, last_consolidated, tokens_to_remove
        )
        if boundary is None or boundary[0] <= last_consolidated:
            # 無可用 user 邊界時，整併剩餘全部 history 尾段
            if last_consolidated >= len(history):
                raise RuntimeError(
                    f"WG-19：past 已空仍無法壓至 target（cost={cost}，target={target}）。"
                    " 請縮短 MEMORY 或調高 config.json 的 token_budget。"
                )
            final_idx = len(history)
        else:
            final_idx = boundary[0]

        pack = history[last_consolidated:final_idx]
        if not pack:
            raise RuntimeError(
                f"WG-19：整併包為空無法推進（cost={cost}，target={target}）。"
            )

        print(
            f"（WG-19 規劃：final_idx={final_idx}，"
            f"待整併 {len(pack)} 則；cost={cost}，target={target}。）"
        )

        print(
            f"（WG-19 歸檔：history[{last_consolidated}:{final_idx}]"
            f" → memory/history.jsonl。）"
        )
        _consolidate_pack(consolidation_llm, pack, session_key, store)
        last_consolidated = final_idx
        # 回到 Phase A 重算（MEMORY 更新後 system 可能變長）


# ---------------------------------------------------------------------------
# WG-22：`Agent` 封裝（核心對外 API）
# ---------------------------------------------------------------------------


class Agent:
    """WG-12～21 執行邏輯之單一入口；不含 CLI `input()`。"""

    def __init__(
        self,
        *,
        workspace: Path,
        config: dict[str, Any],
        session_path: str,
        history: list[BaseMessage],
        session_meta: dict[str, Any] | None,
        last_consolidated: int,
        llm: ChatOpenAI,
        llm_tools: Any,
        store: MemoryStore,
    ) -> None:
        self.workspace = workspace
        self.config = config
        self.session_path = session_path
        self.history = history
        self.session_meta = session_meta
        self.last_consolidated = last_consolidated
        self.llm = llm
        self.llm_tools = llm_tools
        self.store = store

    @classmethod
    def create(
        cls,
        *,
        workspace: str | Path | None = None,
        session_name: str | None = None,
        host_context: str | None = None,
    ) -> Agent:
        config = _ensure_config()
        resolved_workspace = init_workspace(
            _resolve_workspace(workspace, config)
        )
        set_host_context(host_context)
        store = _configure_runtime(resolved_workspace, config)

        session_file = _resolve_session_path(resolved_workspace, session_name)
        session_str = str(session_file)
        history, session_meta = load_session_jsonl(session_str)
        last_consolidated = (
            int(session_meta.get("last_consolidated", 0) or 0)
            if session_meta
            else 0
        )
        llm = _build_llm(config)
        all_tools = _load_all_tools()
        llm_tools = llm.bind_tools(all_tools)
        agent = cls(
            workspace=resolved_workspace,
            config=config,
            session_path=session_str,
            history=history,
            session_meta=session_meta,
            last_consolidated=last_consolidated,
            llm=llm,
            llm_tools=llm_tools,
            store=store,
        )
        from peas_agent.dream_scheduler import ensure_dream_scheduler

        ensure_dream_scheduler(resolved_workspace, config, llm=llm)
        return agent

    def chat(
        self,
        user_text: str,
        *,
        image_path: str | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        image_rel = image_path
        media_type: str | None = None
        if image_rel:
            try:
                media_type = guess_media_type(resolve_project_image_path(image_rel))
            except PermissionError:
                media_type = None

        history_human = history_human_placeholder(user_text, image_rel, media_type)
        human_for_send = build_human_message_for_current_turn(user_text, image_rel)

        session_key = Path(self.session_path).name
        self._maybe_cross_session_each_chat()

        prev_consolidated = self.last_consolidated
        self.last_consolidated = ensure_budget_before_react(
            self.llm,
            self.history,
            self.last_consolidated,
            history_human,
            self.store,
            session_key=session_key,
        )
        if self.last_consolidated != prev_consolidated:
            if self.session_meta is None:
                self.session_meta = _default_metadata()
            self.session_meta = save_session_jsonl(
                self.session_path,
                self.history,
                self.session_meta,
                self.last_consolidated,
            )

        system_text = build_system_prompt(self.store)
        past = self.history[self.last_consolidated:]

        final_text, turn_messages = run_react_turn(
            self.llm_tools,
            system_text,
            past,
            human_for_send,
            history_human,
            on_token=on_token,
        )

        self.history.extend(turn_messages)

        if self.session_meta is None:
            self.session_meta = _default_metadata()
        self.session_meta = save_session_jsonl(
            self.session_path,
            self.history,
            self.session_meta,
            self.last_consolidated,
        )
        print(
            f"（已寫入 {self.session_path!r}，共 {len(self.history)} 則累積訊息；"
            f" last_consolidated={self.last_consolidated}。）"
        )
        return final_text

    def _maybe_cross_session_each_chat(self) -> None:
        dream_cfg = self.config.get("dream", {})
        if not isinstance(dream_cfg, dict):
            return
        if not dream_cfg.get("cross_session_archive", True):
            return
        if dream_cfg.get("cross_session_timing") != "each_chat":
            return
        from peas_agent.dream import Dream

        Dream(self.workspace, self.config, self.llm, store=self.store)._cross_session(
            self.session_path
        )

    def dream(self) -> bool:
        from peas_agent.dream import Dream

        return Dream(
            self.workspace, self.config, self.llm, store=self.store
        ).run(active_session_path=self.session_path)

    def dream_log(self, sha: str | None = None) -> str:
        store = self.store
        if not sha:
            commits = store.git.log(max_entries=5)
            if not commits:
                return "（尚無 Dream git 紀錄）"
            return "\n\n".join(c.format() for c in commits)
        result = store.git.show_commit_diff(sha)
        if result is None:
            return f"找不到 commit {sha!r}"
        commit, diff = result
        return commit.format(diff)

    def dream_restore(self, sha: str | None = None) -> str:
        store = self.store
        if sha is None:
            commits = store.git.log(max_entries=10)
            if not commits:
                return "（尚無可還原的 commit）"
            lines = [f"- `{c.sha}` {c.timestamp} {c.message.splitlines()[0]}" for c in commits]
            return "最近 Dream commits：\n" + "\n".join(lines)
        new_sha = store.git.revert(sha)
        if new_sha:
            from peas_agent.memory_summary import regenerate_memory_summary

            regenerate_memory_summary(store)
            return f"已還原至 {sha} 的父 commit，新 commit `{new_sha}`"
        return f"還原失敗：{sha!r}"

    def memory_summary(self, *, refresh: bool = False) -> str:
        from peas_agent.memory_summary import regenerate_memory_summary

        store = self.store
        if refresh or not store.summary_file.is_file():
            return regenerate_memory_summary(store)
        return store.summary_file.read_text(encoding="utf-8")

    def memory_pin(self, keyword: str) -> None:
        self.store.add_pin(keyword)


get_config_path = _get_config_path
