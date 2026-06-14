# peas-agent-core

PEAS Agent Workshop 核心套件：LangChain ReAct agent、workspace 工具、記憶整併、Skills 與 JSONL session。

## 安裝

```bash
uv add peas-agent-core
```

或在本 repo 開發：

```bash
uv sync
```

## 設定

建立 `~/.peas-agent/config.json`：

```json
{
  "workspace": "~/.peas-agent/workspace",
  "token_budget": 100000,
  "llm": {
    "api_key": "sk-...",
    "model": "gpt-5.4-mini",
    "temperature": 0.7,
    "base_url": ""
  }
}
```

也可透過環境變數 `PEAS_AGENT_WORKSPACE` 或 CLI `-w` 覆寫 workspace。

`workspace` is the agent workspace. It stores durable agent files such as `SOUL.md`, `USER.md`, `AGENTS.md`, `memory/`, `sessions/`, `skills/`, and `tools/`.

The runtime project root is not stored in `config.json`. PEAS Agent infers it from the directory where you launch the CLI by walking upward until it finds `.git`, `pyproject.toml`, or `uv.lock`. If no marker is found, it uses the current directory. Normal coding use does not require extra flags:

```bash
cd C:\path\to\my-project
uv run peas-agent
```

Launching from an initialized project subdirectory still resolves to the parent project root:

```bash
cd C:\path\to\my-project\src\feature
uv run peas-agent
```

Launching from an empty project root also works because no marker falls back to the current directory:

```bash
mkdir C:\path\to\empty-project
cd C:\path\to\empty-project
uv run peas-agent
```

Use `--project-root` / `--project` only when the host process must launch from one directory while asking the agent to work in another:

```bash
uv run peas-agent --project-root C:\path\to\my-project
```

Relative file paths, image paths, and shell commands default to the project root. Prefer project-relative paths for ordinary project files. Use absolute paths for files outside the project root, agent workspace files, or host/debug paths that must be unambiguous. Agent settings and memory remain under `workspace`.

## CLI

```bash
uv run peas-agent
uv run peas-agent -w ./my-workspace -s chat.jsonl
```

## Python API

```python
from peas_agent import Agent

agent = Agent.create(workspace="./my-workspace", session_name="chat.jsonl")
reply = agent.chat("你好")
```

## 開發

```bash
uv sync --group dev
uv run pytest
```

## 與 Streamlit Shell 的關係

Phase 1 僅提供獨立核心套件。`dataset-streamlit-shell` 整合將於 Phase 2 進行。
