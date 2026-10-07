# Handoff：金融業 Google ADK 12 小時工作坊

更新日期：2026-10-07。專案：`c:\Users\mz038\Desktop\peas-agent\peas-agent-core`。

第二天六節已寫進升級版大綱，仍是粗排：MCP、RAG、SKILL、Multi-Agent、SandBox、Deploy。細項先讀大綱那一格再補。不要重開「Skill 與 MCP 誰先上」。

課表細項以升級版大綱為準，不要在交接裡重寫整張表：

`c:\Users\mz038\Desktop\peas-agent\peas-agent-core\金融業-ADK工作坊-12小時-升級.md`

## 以哪份檔為準

- Markdown 與 Word 應一致：`G:\我的雲端硬碟\Obsidian\Agent\raw\materials\神通科技\金融業-ADK工作坊-12小時-升級.docx`
- Word 若正開著會存檔失敗。先改 Markdown。到 2026-10-07，Word 尚未同步這幾天的改動。
- 長稿 `G:\我的雲端硬碟\Obsidian\Agent\raw\materials\神通科技\金融業-ADK工作坊-12小時.md` 堂次可能對不上。不要拿它覆蓋升級版。
- 不要改 `G:\我的雲端硬碟\Obsidian\Agent\raw\materials\神通科技\台南一中\南一中-Agent課程-12堂.md`。
- SEQ／PAR／LOOP／RTR 的四句對照來自 `G:\我的雲端硬碟\Obsidian\Agent\raw\materials\神通科技\台南一中\台南一中_教學課程大綱_agent新版.docx` 的 2026.11.11 第 4 堂。只借形狀，情境用禾豐進件。

## 課表規則（已定）

- 同一天節數往下累加。第一天第 1 到第 6 節，第二天再從第 1 節數。
- 第 3、第 4 節是同一圈 ReAct，不拆成 Lv6 工具和 Lv7 先查再講。第 4 節不另加機制。
- 第 5 節主題是 Prompt Chaining / Parallelization（SEQ / PAR）。
- 第 6 節是 LOOP／RTR，Loop 寫完才接 RTR。RTR 不要再搬到第二天。
- LOOP／RTR 佔第一天第 6 節。第二天第 6 節是 Deploy。
- 舊 Route、Confirm、Lv8、獨立 Demo 不再佔第二天的格子。確認鍵沒有併進 Deploy。
- 第二天第 4 節是 Multi-Agent：父層把覆核員當工具叫來，問完自己寫回經辦。第一天 RTR 仍是 `sub_agents` 把報告交出去。
- 直接打 `adk` 會失敗，前面加 `uv run`。課堂用 `--port 8010`。
- `.env` 的鑰匙不要讀出來，也不要寫進交接、大綱、git。

## 情境（口頭故事）

經辦打「禾豐食品要申請週轉金 800 萬」。先收件，再同時查主檔、既有額度、警示、變更登記。既有額度 300 萬只能來自查詢。然後寫有固定段落的初審報告。不合格最多改兩輪，仍不合格就留在經辦，不送部門。

合格後才送部門。警示命中去覆核（山海）。缺件不是「無」去補件（北岸）。兩個都有先覆核。其餘留草稿（禾豐）。都不送審。經辦收件、查、寫報告，沒有准駁權。

## 程式

`bank_assistant/agent.py` 維持單顆 `root_agent`，給 `adk web`。後面每一層各一支，不回寫 `agent.py`。

| 檔 | 做什麼 |
|---|---|
| `queries.py` | 四支查詢與 `CASES`。300 萬只在這裡 |
| `seq.py` | 收件、一次查完、寫意見。`session_id` 預設沿用 s1 |
| `par.py` | 收件後四支同時查。對話編號 `par` |
| `loop.py` | 同一條再寫 `ReviewReport`，最多兩輪。對話編號 `loop` |
| `rtr.py` | 報告之後，聊天模型當 `route`，`sub_agents` 交給 review／supplement／draft。對話編號 `rtr` |
| `jev.py` | 示範。`JevRoute` 打 `POST {BASE_URL}/decisions`，不包成 tool。目前用山海範例報告單跑，還沒排進 `revise` 後面 |

模型是 `OpenAILlm`，從 `.env` 讀 `MODEL_NAME`、`BASE_URL`、`VCR_API_KEY`。決策模型環境變數是 `DECISION_MODEL`，預設 `vcr-auto`。指定 Jev 的 id 是 `openrouter@typesafe/jev-1.13`。規格在 `D:\Work\Python\vans_coding_router\docs\openapi\chat-completions-and-responses.openapi.yaml` 的 `/v1/decisions`。

`output_key` 只存該顆最後一次回答。`{intake.company}` 不會拆欄。要單欄就用 callback 抄到 `state["company"]`。`sub_agents` 是把報告交出去。把 Agent 當 tool 是問完還由父層轉述。這節用前者。

Jev 是決策模型，不寫封面。封面仍由部門那顆文字模型寫。

## 下一輪怎麼做

討論用短句。先讀大綱那一格再改。不要另寫一套課。

未決：第二天六格仍是粗排。MCP、Multi-Agent、SandBox、Deploy 還沒有課堂步驟。RAG 與 SKILL 沿用原驗收。Word 尚未同步。

## Suggested skills

- 改升級版 Word 時讀 `C:\Users\mz038\.cursor\skills\document-skills\docx\SKILL.md`。
- 不需要南一中帶班 skill，也不要改那份 12 堂教案。
