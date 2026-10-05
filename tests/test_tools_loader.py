"""Tests for workspace tool discovery, loading, and Agent.create integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_core.tools import tool

from peas_agent.core import _get_builtin_tools, _load_all_tools, init_workspace
from peas_agent.tools_loader import (
    ToolsLoader,
    discover_tool_files,
    load_tools_from_file,
    merge_tools,
)
from peas_agent.prompt_templates import sync_workspace_templates


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return init_workspace(tmp_path / "workspace")


def test_init_workspace_creates_tools_dir(workspace: Path) -> None:
    assert (workspace / "tools").is_dir()


def test_sync_workspace_templates_scaffolds_example_tool(workspace: Path) -> None:
    sync_workspace_templates(workspace, silent=True)
    example = workspace / "tools" / "example_calc" / "tool.py"
    assert example.is_file()
    assert "@tool" in example.read_text(encoding="utf-8")


def test_discover_tool_files_supports_flat_and_nested(workspace: Path) -> None:
    tools_dir = workspace / "tools"
    (tools_dir / "flat_tool.py").write_text("# flat\n", encoding="utf-8")
    nested = tools_dir / "nested"
    nested.mkdir()
    (nested / "tool.py").write_text("# nested\n", encoding="utf-8")
    (tools_dir / "_private.py").write_text("# skip\n", encoding="utf-8")

    files = discover_tool_files(tools_dir)
    assert any(p.name == "flat_tool.py" for p in files)
    assert any(p.name == "tool.py" and p.parent.name == "nested" for p in files)
    assert all(p.name != "_private.py" for p in files)


def test_load_tools_from_file_loads_decorated_tool(workspace: Path) -> None:
    tool_file = workspace / "tools" / "calc_bmi.py"
    tool_file.write_text(
        """
from langchain_core.tools import tool

@tool
def calc_bmi(weight_kg: float, height_m: float) -> str:
    \"\"\"計算 BMI。\"\"\"
    bmi = weight_kg / (height_m ** 2)
    return f\"BMI: {bmi:.1f}\"
""".strip(),
        encoding="utf-8",
    )

    tools, entries, error = load_tools_from_file(tool_file, workspace=workspace)
    assert error is None
    assert len(tools) == 1
    assert tools[0].name == "calc_bmi"
    assert entries[0].path == "tools/calc_bmi.py"
    assert "BMI" in entries[0].description


def test_load_tools_from_file_reports_syntax_error(workspace: Path) -> None:
    tool_file = workspace / "tools" / "broken.py"
    tool_file.write_text("def oops(:\n", encoding="utf-8")

    tools, entries, error = load_tools_from_file(tool_file, workspace=workspace)
    assert tools == []
    assert entries == []
    assert error is not None
    assert "broken.py" in error


def test_merge_tools_skips_builtin_name_conflicts() -> None:
    @tool
    def read_file(path: str) -> str:
        """student override attempt"""
        return path

    @tool
    def student_tool(x: int) -> str:
        """student tool"""
        return str(x)

    warnings: list[str] = []
    merged = merge_tools(_get_builtin_tools(), [read_file, student_tool], warnings=warnings)
    names = {t.name for t in merged}
    assert "student_tool" in names
    assert len([t for t in merged if t.name == "read_file"]) == 1
    assert any("read_file" in w for w in warnings)


def test_tools_loader_isolates_broken_files(workspace: Path) -> None:
    tools_dir = workspace / "tools"
    (tools_dir / "good.py").write_text(
        """
from langchain_core.tools import tool

@tool
def good_tool() -> str:
    \"\"\"ok\"\"\"
    return \"ok\"
""".strip(),
        encoding="utf-8",
    )
    (tools_dir / "bad.py").write_text("syntax error !!!", encoding="utf-8")

    loader = ToolsLoader(workspace)
    result = loader.load_all()
    loaded_names = {t.name for t in result.tools}
    assert "good_tool" in loaded_names
    assert any("bad.py" in w for w in result.warnings)


def _portal_tool(name: str, marker: str):
    @tool(name)
    def _portal(query: str) -> str:
        """portal tool"""
        return marker

    return _portal


def _write_portal_config(project: Path, url: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / "peas-mcp.json").write_text(
        """
{
  "servers": {
    "vans-mcp": {
      "type": "http",
      "url": "%s",
      "headers": {"Authorization": "Bearer test-key"}
    }
  }
}
""".strip()
        % url,
        encoding="utf-8",
    )


def test_load_all_tools_includes_portal_tools_from_project_root(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "student-project"
    _write_portal_config(project, "http://127.0.0.1:9/mcp/")
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", project)
    monkeypatch.setattr("peas_agent.core.TOOLS_LOADER", ToolsLoader(workspace))

    seen: dict[str, str] = {}

    async def fake_fetch(connections: dict) -> list:
        seen["url"] = connections["vans-mcp"]["url"]
        return [_portal_tool("notion_search_pages", "from-portal")]

    monkeypatch.setattr("peas_agent_mcp.registry.fetch_tools_async", fake_fetch)

    names = {t.name for t in _load_all_tools()}
    assert "notion_search_pages" in names
    assert "read_file" in names
    assert seen["url"] == "http://127.0.0.1:9/mcp/"


def test_load_all_tools_rereads_portal_config_for_each_project_root(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_portal_config(first, "http://127.0.0.1:9/mcp/")
    _write_portal_config(second, "http://127.0.0.1:10/mcp/")
    monkeypatch.setattr("peas_agent.core.TOOLS_LOADER", ToolsLoader(workspace))
    seen: list[str] = []

    async def fake_fetch(connections: dict) -> list:
        seen.append(connections["vans-mcp"]["url"])
        return [_portal_tool("notion_search_pages", "from-portal")]

    monkeypatch.setattr("peas_agent_mcp.registry.fetch_tools_async", fake_fetch)

    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", first)
    _load_all_tools()
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", second)
    _load_all_tools()

    assert seen == [
        "http://127.0.0.1:9/mcp/",
        "http://127.0.0.1:10/mcp/",
    ]


def test_portal_load_failure_keeps_builtin_tools(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "broken-project"
    project.mkdir()
    (project / "peas-mcp.json").write_text("{", encoding="utf-8")
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", project)
    monkeypatch.setattr("peas_agent.core.TOOLS_LOADER", ToolsLoader(workspace))

    names = {t.name for t in _load_all_tools()}
    assert "read_file" in names
    assert "notion_search_pages" not in names
    assert "Portal 工具載入失敗" in capsys.readouterr().out


def test_portal_tools_lose_to_builtin_and_win_over_workspace(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "student-project"
    _write_portal_config(project, "http://127.0.0.1:9/mcp/")
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", project)
    monkeypatch.setattr("peas_agent.core.TOOLS_LOADER", ToolsLoader(workspace))
    (workspace / "tools" / "shadow.py").write_text(
        """
from langchain_core.tools import tool

@tool
def notion_search_pages(query: str) -> str:
    \"\"\"workspace shadow\"\"\"
    return "from-workspace"
""".strip(),
        encoding="utf-8",
    )
    portal_read = _portal_tool("read_file", "from-portal")
    portal_notion = _portal_tool("notion_search_pages", "from-portal")

    async def fake_fetch(connections: dict) -> list:
        return [portal_read, portal_notion]

    monkeypatch.setattr("peas_agent_mcp.registry.fetch_tools_async", fake_fetch)

    tools = _load_all_tools()
    by_name = {t.name: t for t in tools}
    assert by_name["read_file"] is not portal_read
    assert by_name["notion_search_pages"] is portal_notion
    assert by_name["notion_search_pages"].invoke({"query": "x"}) == "from-portal"
    warning = capsys.readouterr().out
    assert "portal tool 'read_file'" in warning
    assert "workspace tool 'notion_search_pages'" in warning


def test_dream_tools_do_not_load_portal_tools(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from peas_agent.dream import _build_dream_tools

    called = False

    async def fake_fetch(connections: dict) -> list:
        nonlocal called
        called = True
        return [_portal_tool("notion_search_pages", "from-portal")]

    monkeypatch.setattr("peas_agent_mcp.registry.fetch_tools_async", fake_fetch)

    names = {t.name for t in _build_dream_tools(workspace)}
    assert "read_file" in names
    assert called is False
    assert "notion_search_pages" not in names


def test_load_all_tools_rebuilds_registry(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("peas_agent.core.TOOLS_LOADER", ToolsLoader(workspace))
    (workspace / "tools" / "hello.py").write_text(
        """
from langchain_core.tools import tool

@tool
def hello_world() -> str:
    \"\"\"Say hello.\"\"\"
    return \"hello\"
""".strip(),
        encoding="utf-8",
    )

    all_tools = _load_all_tools()
    names = {t.name for t in all_tools}
    assert "hello_world" in names
    assert "read_file" in names

    from peas_agent.core import _TOOL_BY_NAME

    assert "hello_world" in _TOOL_BY_NAME


def test_agent_create_binds_workspace_tools(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (workspace / "tools" / "greet.py").write_text(
        """
from langchain_core.tools import tool

@tool
def greet(name: str) -> str:
    \"\"\"Greet someone.\"\"\"
    return f\"hi {name}\"
""".strip(),
        encoding="utf-8",
    )

    cfg = {
        "workspace": str(workspace),
        "token_budget": 100000,
        "llm": {"api_key": "test-key", "model": "gpt-5.4-mini", "temperature": 0.2},
    }

    class FakeBound:
        def __init__(self, tools: list) -> None:
            self.tools = tools

    class FakeLLM:
        def bind_tools(self, tools: list) -> FakeBound:
            self.bound_tools = tools
            return FakeBound(tools)

    fake_llm = FakeLLM()

    with (
        patch("peas_agent.core._ensure_config", return_value=cfg),
        patch("peas_agent.core._build_llm", return_value=fake_llm),
        patch("peas_agent.core.load_session_jsonl", return_value=([], None)),
    ):
        from peas_agent.core import Agent

        agent = Agent.create(workspace=workspace)

    bound_names = {t.name for t in fake_llm.bound_tools}
    assert "greet" in bound_names
    assert agent.workspace == workspace.resolve()
