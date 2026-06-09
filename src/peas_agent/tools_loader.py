"""Load student-defined LangChain tools from workspace/tools/."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


@dataclass
class ToolEntry:
    name: str
    path: str
    description: str


@dataclass
class LoadResult:
    tools: list[Any]
    entries: list[ToolEntry]
    warnings: list[str]


def discover_tool_files(tools_dir: Path) -> list[Path]:
    """Return workspace tool modules: tools/*.py and tools/*/tool.py."""
    if not tools_dir.is_dir():
        return []

    files: list[Path] = []
    for path in sorted(tools_dir.glob("*.py")):
        if not path.name.startswith("_"):
            files.append(path)
    for path in sorted(tools_dir.glob("*/tool.py")):
        if not path.parent.name.startswith("_"):
            files.append(path)
    return files


def _is_langchain_tool(obj: Any) -> bool:
    return (
        obj is not None
        and hasattr(obj, "name")
        and hasattr(obj, "invoke")
        and callable(getattr(obj, "invoke", None))
        and hasattr(obj, "description")
    )


def _import_module_from_path(path: Path) -> ModuleType:
    module_name = f"_peas_workspace_tool_{path.stem}_{abs(hash(path)) & 0xFFFFFFFF:08x}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot create module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _collect_tools_from_module(module: ModuleType) -> list[Any]:
    if hasattr(module, "TOOLS"):
        exported = getattr(module, "TOOLS")
        if isinstance(exported, (list, tuple)):
            return [obj for obj in exported if _is_langchain_tool(obj)]

    tools: list[Any] = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if _is_langchain_tool(obj):
            tools.append(obj)
    return tools


def load_tools_from_file(path: Path, *, workspace: Path) -> tuple[list[Any], list[ToolEntry], str | None]:
    """Load tools from one file. Returns (tools, entries, error_message)."""
    try:
        module = _import_module_from_path(path)
    except Exception as e:
        return [], [], f"{path.name}: {e}"

    tools = _collect_tools_from_module(module)
    if not tools:
        return [], [], f"{path.name}: no @tool definitions found"

    try:
        rel_path = path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        rel_path = path.as_posix()

    entries = [
        ToolEntry(
            name=str(tool.name),
            path=rel_path,
            description=str(getattr(tool, "description", "") or tool.name),
        )
        for tool in tools
    ]
    return tools, entries, None


def merge_tools(
    builtin: list[Any],
    workspace: list[Any],
    *,
    warnings: list[str] | None = None,
) -> list[Any]:
    """Merge workspace tools into builtins; builtins win on name conflicts."""
    merged = list(builtin)
    seen = {str(tool.name) for tool in builtin}
    for tool in workspace:
        name = str(tool.name)
        if name in seen:
            if warnings is not None:
                warnings.append(
                    f"Skipped workspace tool {name!r}: conflicts with a builtin tool"
                )
            continue
        merged.append(tool)
        seen.add(name)
    return merged


class ToolsLoader:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.tools_dir = self.workspace / "tools"
        self._last_result: LoadResult | None = None

    def load_all(self) -> LoadResult:
        tools: list[Any] = []
        entries: list[ToolEntry] = []
        warnings: list[str] = []

        for path in discover_tool_files(self.tools_dir):
            loaded, file_entries, error = load_tools_from_file(
                path, workspace=self.workspace
            )
            if error:
                warnings.append(error)
                continue
            tools.extend(loaded)
            entries.extend(file_entries)

        result = LoadResult(tools=tools, entries=entries, warnings=warnings)
        self._last_result = result
        return result

    def list_entries(self) -> list[ToolEntry]:
        if self._last_result is None:
            self.load_all()
        assert self._last_result is not None
        return list(self._last_result.entries)

    def last_warnings(self) -> list[str]:
        if self._last_result is None:
            self.load_all()
        assert self._last_result is not None
        return list(self._last_result.warnings)


def build_tools_summary(entries: list[ToolEntry]) -> str:
    if not entries:
        return ""
    lines = [f"- **{e.name}** — {e.description} `{e.path}`" for e in entries]
    return "\n".join(lines)
