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
