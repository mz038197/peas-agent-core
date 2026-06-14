# 代理人指令

## 工作區指引

將這個檔案用於記錄此工作區的專案偏好、重複性的工作流程慣例，以及希望代理人記住的指示。請將關於使用者的長期且穩定事實放在 `USER.md`，將個性與行為放在 `SOUL.md`，將長期記憶放在 `memory/MEMORY.md`。

## 工作坊慣例

- 這個專案使用 **uv** 管理 Python 相依套件。若要修改使用者專案相依套件，使用 `exec` 執行 `uv add <package>`；`exec` 預設在 project root 執行。不要使用 `pip install`。
- 可重複執行的 Agent 輔助腳本放在 **agent workspace** 的 `scripts/<name>.py`。建立或編輯時使用 workspace 的**絕對路徑**（相對路徑會解析到 project root，不會寫進 workspace）。
- 使用者專案程式放在 **project root**；用 `write_file` / `edit_file` 時優先使用 project-relative 路徑，例如 `src/app.py`。
- 自訂 skill 放在 agent workspace 的 `skills/<name>/SKILL.md`；讀寫時使用 workspace 絕對路徑。
- 自訂 tool 放在 agent workspace 的 `tools/<name>.py` 或 `tools/<name>/tool.py`；讀寫時使用 workspace 絕對路徑。使用 LangChain `@tool` 裝飾器定義。啟動時會自動載入並綁定為 function calling；修改後需重啟 agent。不可覆寫內建 tool 名稱（如 `read_file`、`exec`）。
- 長期事實會在上下文預算管理期間自動彙整到 agent workspace 的 `memory/MEMORY.md`（WG-19）。不要把 MEMORY 當成暫時性任務狀態的草稿區。

## 檔案編輯

- 小型且精確、可直接從 `read_file` 複製的替換內容，使用 `edit_file`。
- 新檔案或刻意整檔重寫時，使用 `write_file`。
- 除非使用者直接下達刪除檔案的指令，否則在執行任何刪除檔案操作前，必須先取得使用者明確同意。