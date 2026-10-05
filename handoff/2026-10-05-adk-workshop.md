# Handoff：金融業 Google ADK 12 小時工作坊

日期：2026-10-05。專案：`c:\Users\mz038\Desktop\peas-agent\peas-agent-core`。

下一輪從大綱的**第一天第 3 節**接著討論。使用者要一節一節改，先讀升級版原文，再改 `bank_assistant/agent.py`。不要另寫一套課。

## 以哪份檔為準

課表以這兩份為準，內容應一致：

- `c:\Users\mz038\Desktop\peas-agent\peas-agent-core\金融業-ADK工作坊-12小時-升級.md`
- `G:\我的雲端硬碟\Obsidian\Agent\raw\materials\神通科技\金融業-ADK工作坊-12小時-升級.docx`

Word 若正開著會存檔失敗。先改 Markdown，Word 能寫再同步。

長稿 `G:\我的雲端硬碟\Obsidian\Agent\raw\materials\神通科技\金融業-ADK工作坊-12小時.md` 有舊段落，堂次和節次可能對不上。不要拿它覆蓋升級版。

不要改 `G:\我的雲端硬碟\Obsidian\Agent\raw\materials\神通科技\台南一中\南一中-Agent課程-12堂.md`。

## 課表規則（已定）

- 主線是合成進件：禾豐食品、週轉金 800 萬。模型不寫核貸。既有額度 300 萬只能來自之後的工具，第 1 堂講出來算編的。
- 同一天節數往下累加。第一天第 1 節到第 6 節，第二天再從第 1 節數。堂次仍是第 1 堂到第 6 堂。
- 第 1 堂第 1 節已合併原第 2 節（兩套身份）。後面各節上移一格。第 6 堂第 2 節（第二天第 6 節）空著。Demo 在第二天第 5 節。
- 第 1 堂第 2 節是記憶與 session 儲存，不掛工具。
- 三種執行都寫在第 1 堂第 1 節，都要跑過：
  - `uv run adk web bank_assistant --port 8010`
  - `uv run adk run bank_assistant`
  - `uv run python bank_assistant/agent.py`
- 直接打 `adk` 會失敗。指令在專案的 `.venv`，前面要加 `uv run`。
- 8000 埠曾被另一支 Python 佔用。課堂指令用 `--port 8010`。

## 程式現況

實作只在 `bank_assistant/agent.py`。`google-adk` 已用 `uv add` 進 `pyproject.toml`，裝到的版本是 2.11.0。

- 模型走 Vans router：`OpenAILlm` 從 `.env` 讀 `MODEL_NAME`（`vcr-auto`）、`BASE_URL`（`https://ai.vanscoding.com/v1`）、`VCR_API_KEY`。`_load_env()` 在建立 `root_agent` 之前。第一天第 1 節已寫進升級版大綱。
- 溫度不要寫成 `Agent(temperature=0)`。要寫 `generate_content_config=types.GenerateContentConfig(temperature=0)`。
- 對話迴圈是 `input()` 加 `Runner.run_debug(..., session_id="s1")`。這只給課堂在終端機試。正式環境留 `root_agent`，改走 `run_async`，不要靠 `input()`。
- `SESSION_STORE` 預設 `sqlite`，檔在 `bank_assistant/.adk/session.db`。另有 `memory`、`postgres`。PostgreSQL 網址必須是 `postgresql+asyncpg://`。`asyncpg` 尚未安裝。
- 這版 ADK 的 Runner 類別只有 `Runner` 和 `InMemoryRunner`。沒有 MongoDB session 服務。SQL 只有 SQLite、PostgreSQL、MySQL、MariaDB、SQL Server。
- `.env` 已存在且在 `.gitignore`。不要把鑰匙讀出來或寫進交接、大綱、git。`.adk` 也已忽略。

## 下一輪怎麼做

使用者說「讀升級的」時，先讀上面那份 Markdown 或 Word 的那一格，不要自己重寫課程。

討論語氣要短句、一步一件事。他們要的是 Google ADK 從這份 `agent.py` 往下加，不是另做固定句示範。

第 3 節（第一天，第 2 堂）主題是工具：四個查詢函式，禾豐額度 300 萬必須有工具紀錄。細節以大綱那一格為準。

## Suggested skills

- 改升級版 Word 時讀 `C:\Users\mz038\.cursor\skills\document-skills\docx\SKILL.md`。
- 不需要南一中帶班 skill，也不要改那份 12 堂教案。
