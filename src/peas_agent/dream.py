"""Two-phase Dream memory processor."""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from peas_agent.memory_archive import cross_session_archive
from peas_agent.memory_store import MemoryStore, configure_memory_store, get_memory_store
from peas_agent.memory_summary import regenerate_memory_summary

PACKAGE_DIR = Path(__file__).resolve().parent
DREAM_PHASE1_PATH = PACKAGE_DIR / "prompts" / "dream_phase1.md"
DREAM_PHASE2_PATH = PACKAGE_DIR / "prompts" / "dream_phase2.md"

_EPHEMERAL_MEMORY_PATTERNS = (
    "數到",
    "數數",
    "每秒數",
    "每秒",
    "手動接續",
    "連續數",
    "不要中斷",
    "不喜歡計數突然中斷",
)

_workspace_locks: dict[str, threading.Lock] = {}
_lock_registry = threading.Lock()


def get_workspace_lock(workspace: Path) -> threading.Lock:
    key = str(workspace.expanduser().resolve())
    with _lock_registry:
        if key not in _workspace_locks:
            _workspace_locks[key] = threading.Lock()
        return _workspace_locks[key]


def get_dream_config(config: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "enabled": True,
        "cron": "0 */2 * * *",
        "model": None,
        "max_batch_size": 20,
        "max_iterations": 10,
        "cross_session_archive": True,
        "cross_session_timing": "before_dream",
        "recent_history_max": 50,
        "summary_mode": "template",
    }
    raw = config.get("dream", {})
    if isinstance(raw, dict):
        defaults.update(raw)
    return defaults


class Dream:
    def __init__(
        self,
        workspace: Path,
        config: dict[str, Any],
        llm: ChatOpenAI,
        *,
        store: MemoryStore | None = None,
    ) -> None:
        self.workspace = workspace.expanduser().resolve()
        self.config = config
        self.llm = llm
        self.dream_cfg = get_dream_config(config)
        if store is not None:
            self.store = store
        else:
            try:
                self.store = get_memory_store(self.workspace)
            except RuntimeError:
                self.store = configure_memory_store(self.workspace)

    def run(self, *, active_session_path: str | None = None) -> bool:
        lock = get_workspace_lock(self.workspace)
        if not lock.acquire(blocking=False):
            return False
        try:
            return self._run_locked(active_session_path=active_session_path)
        finally:
            lock.release()

    def _run_locked(self, *, active_session_path: str | None) -> bool:
        if self.dream_cfg.get("cross_session_archive", True):
            if self.dream_cfg.get("cross_session_timing", "before_dream") == "before_dream":
                self._cross_session(active_session_path)

        last_cursor = self.store.get_last_dream_cursor()
        entries = self.store.read_unprocessed_history(since_cursor=last_cursor)
        if not entries:
            return False

        batch_size = int(self.dream_cfg.get("max_batch_size", 20))
        batch = entries[:batch_size]

        history_text = "\n".join(
            f"[{e.get('timestamp', '?')}]"
            + (f" [{e['session_key']}]" if e.get("session_key") else "")
            + f" {e.get('content', '')}"
            for e in batch
        )

        current_date = datetime.now().strftime("%Y-%m-%d")
        pinned = self.store.read_pinned()
        pinned_text = "\n".join(f"- {p}" for p in pinned) if pinned else "(none)"

        file_context = self._file_context(current_date)
        phase1_user = (
            f"## Conversation History\n{history_text}\n\n"
            f"## Pinned Items\n{pinned_text}\n\n{file_context}"
        )

        try:
            print("（Dream Phase 1：分析 history…）", flush=True)
            phase1_response = self.llm.invoke(
                [
                    SystemMessage(content=DREAM_PHASE1_PATH.read_text(encoding="utf-8")),
                    HumanMessage(content=phase1_user),
                ]
            )
            analysis = (
                phase1_response.content
                if isinstance(phase1_response.content, str)
                else str(phase1_response.content)
            )
        except Exception:
            return False

        analysis = analysis.strip()
        analysis = self._filter_analysis(analysis)
        if self._is_skip_only(analysis):
            self._finalize(batch, had_changes=False)
            return True

        print("（Dream Phase 2：更新記憶檔…）", flush=True)
        had_changes = self._run_phase2(analysis, file_context)

        self._finalize(batch, had_changes=had_changes)
        return True

    def _cross_session(self, active_session_path: str | None) -> None:
        from peas_agent.core import (
            _message_plaintext,
            load_session_jsonl,
            save_session_jsonl,
        )

        cross_session_archive(
            self.workspace,
            active_session_path or "",
            self.llm,
            self.store,
            load_session_jsonl=load_session_jsonl,
            save_session_jsonl=save_session_jsonl,
            message_plaintext=_message_plaintext,
        )

    def _file_context(self, current_date: str) -> str:
        memory = self.store.read_memory() or "(empty)"
        soul = self.store.read_soul() or "(empty)"
        user = self.store.read_user() or "(empty)"
        return (
            f"## Current Date\n{current_date}\n\n"
            f"## Current MEMORY.md\n{memory}\n\n"
            f"## Current SOUL.md\n{soul}\n\n"
            f"## Current USER.md\n{user}"
        )

    @staticmethod
    def _is_skip_only(analysis: str) -> bool:
        lines = [line.strip() for line in analysis.splitlines() if line.strip()]
        if not lines:
            return True
        non_skip = [line for line in lines if line.upper() != "[SKIP]"]
        return not non_skip

    @staticmethod
    def _filter_analysis(analysis: str) -> str:
        kept: list[str] = []
        for line in analysis.splitlines():
            stripped = line.strip()
            if _is_ephemeral_user_or_soul_memory(stripped):
                continue
            kept.append(line)
        return "\n".join(kept).strip()

    def _run_phase2(self, analysis: str, file_context: str) -> bool:
        from peas_agent.core import SkillsLoader, run_dream_react_turn

        phase2_template = DREAM_PHASE2_PATH.read_text(encoding="utf-8")
        phase2_system = phase2_template.replace(
            "{{ skill_creator_path }}",
            f"builtin_skills/skill-creator/SKILL.md",
        )

        loader = SkillsLoader(self.workspace)
        skills = loader.list_skills()
        skills_section = ""
        if skills:
            skills_section = "\n\n## Existing Skills\n" + "\n".join(
                f"- {e.name} — {e.description}" for e in skills
            )

        phase2_user = f"## Analysis Result\n{analysis}\n\n{file_context}{skills_section}"
        tools = _build_dream_tools(self.workspace)
        tools_by_name = {t.name: t for t in tools}

        def tool_runner(name: str, args: dict[str, Any]) -> str:
            tool_obj = tools_by_name.get(name)
            if tool_obj is None:
                return f"Error: unknown tool {name!r}"
            try:
                return str(tool_obj.invoke(dict(args or {})))
            except Exception as e:
                return f"Error running tool {name}: {e}"

        max_iter = int(self.dream_cfg.get("max_iterations", 10))
        llm_tools = self.llm.bind_tools(tools)

        def progress(iteration: int) -> None:
            print(f"（Dream Phase 2：第 {iteration} 輪…）", flush=True)

        _, tool_events = run_dream_react_turn(
            llm_tools,
            phase2_system,
            phase2_user,
            max_iterations=max_iter,
            tool_runner=tool_runner,
            on_iteration=progress,
        )
        return any(ev.get("status") == "ok" for ev in tool_events)

    def _finalize(self, batch: list[dict[str, Any]], *, had_changes: bool) -> None:
        new_cursor = int(batch[-1]["cursor"])
        self.store.set_last_dream_cursor(new_cursor)
        self.store.compact_history()

        if had_changes and self.store.git.is_initialized():
            ts = batch[-1].get("timestamp", "")
            self.store.git.auto_commit(f"dream: {ts}")

        regenerate_memory_summary(self.store)


def _build_dream_tools(workspace: Path) -> list[Any]:
    pkg = PACKAGE_DIR

    def _resolve_read(path: str) -> Path:
        raw = Path(path)
        if raw.is_absolute():
            target = raw.expanduser().resolve()
        else:
            target = (workspace / path).expanduser().resolve()
        if target.is_file():
            return target
        pkg_target = (pkg / path).expanduser().resolve()
        if pkg_target.is_file():
            return pkg_target
        return target

    def _resolve_ws(path: str) -> Path:
        raw = Path(path)
        if raw.is_absolute():
            return raw.expanduser().resolve()
        return (workspace / path).expanduser().resolve()

    @tool("read_file")
    def dream_read_file(path: str, offset: int = 1, limit: int = 200) -> str:
        """Read UTF-8 text file with line numbers."""
        try:
            target = _resolve_read(path)
            if not target.is_file():
                return f"Error: not a file: {path}"
            lines = target.read_text(encoding="utf-8").splitlines()
            start = max(offset - 1, 0)
            end = min(start + limit, len(lines))
            return "\n".join(f"{i + 1}| {line}" for i, line in enumerate(lines[start:end], start))
        except Exception as e:
            return f"Error: {e}"

    @tool("write_file")
    def dream_write_file(path: str, content: str) -> str:
        """Write file under skills/ only."""
        try:
            target = _resolve_ws(path)
            rel = target.relative_to(workspace)
            parts = rel.as_posix().split("/")
            if not parts or parts[0] != "skills":
                return "Error: dream write_file only allows skills/ paths"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"wrote {len(content)} characters to {path}"
        except Exception as e:
            return f"Error: {e}"

    @tool("edit_file")
    def dream_edit_file(
        path: str, old_text: str, new_text: str, replace_all: bool = False
    ) -> str:
        """Edit MEMORY/SOUL/USER under workspace."""
        try:
            target = _resolve_ws(path)
            rel = target.relative_to(workspace).as_posix()
            allowed = {"SOUL.md", "USER.md", "memory/MEMORY.md"}
            if rel not in allowed:
                return f"Error: dream edit_file only allows {sorted(allowed)}"
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

    return [dream_read_file, dream_write_file, dream_edit_file]


def _is_ephemeral_user_or_soul_memory(line: str) -> bool:
    upper = line.upper()
    if not (upper.startswith("[FILE] USER:") or upper.startswith("[FILE] SOUL:")):
        return False
    return any(pattern in line for pattern in _EPHEMERAL_MEMORY_PATTERNS)
