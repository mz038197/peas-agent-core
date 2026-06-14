from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from peas_agent.core import (
    exec_workspace,
    init_workspace,
    resolve_project_image_path,
    resolve_project_path,
    write_file,
)


def test_relative_file_paths_resolve_to_project_root(tmp_path: Path, monkeypatch) -> None:
    workspace = init_workspace(tmp_path / "agent-workspace")
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr("peas_agent.core.WORKSPACE", workspace.resolve())
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", project.resolve())

    write_file.invoke({"path": "src/app.py", "content": "print('project')\n"})

    assert (project / "src" / "app.py").read_text(encoding="utf-8") == "print('project')\n"
    assert not (workspace / "src" / "app.py").exists()


def test_resolve_project_path_keeps_absolute_paths(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.txt"
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", project.resolve())

    assert resolve_project_path(str(outside)) == outside.resolve()


def test_image_relative_paths_resolve_to_project_root(tmp_path: Path, monkeypatch) -> None:
    workspace = init_workspace(tmp_path / "agent-workspace")
    project = tmp_path / "project"
    project.mkdir()
    image = project / "screen.png"
    image.write_bytes(b"not-real-png")
    monkeypatch.setattr("peas_agent.core.WORKSPACE", workspace.resolve())
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", project.resolve())

    assert resolve_project_image_path("screen.png") == image.resolve()


def test_exec_defaults_to_project_root(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", project.resolve())

    with patch("peas_agent.core.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b"ok"
        mock_run.return_value.stderr = b""
        exec_workspace.invoke({"command": "echo hi"})

    assert mock_run.call_args.kwargs["cwd"] == str(project.resolve())
