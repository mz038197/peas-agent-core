# 代理人指令

## 工作區指引

將這個檔案用於記錄此工作區的專案偏好、重複性的工作流程慣例，以及希望代理人記住的指示。請將關於使用者的長期且穩定事實放在 `USER.md`，將個性與行為放在 `SOUL.md`，將長期記憶放在 `memory/MEMORY.md`。

## 工作坊慣例

- 這個專案使用 **uv** 管理 Python 相依套件。若要修改使用者專案相依套件，使用 `exec` 執行 `uv add <package>`，並以 `cwd` 指向該專案根目錄；不要使用 `pip install`。
- 對於可重複執行的 Agent 輔助腳本，放在 workspace 的 `scripts/<name>.py`；使用 `write_file` 建立後，以 `exec uv run python scripts/<name>.py` 執行。
- 若腳本是要成為使用者專案的一部分，才放到該專案目錄，並使用絕對路徑或 `exec` 的 `cwd` 指向專案根目錄。
- 自訂 skill 放在 workspace 的 `skills/<name>/SKILL.md`；內建 skill 由套件提供，不必自行建立。
- 自訂 tool 放在 `tools/<name>.py` 或 `tools/<name>/tool.py`，使用 LangChain `@tool` 裝飾器定義。啟動時會自動載入並綁定為 function calling；修改後需重啟 agent。不可覆寫內建 tool 名稱（如 `read_file`、`exec`）。
- 長期事實會在上下文預算管理期間自動彙整到 `memory/MEMORY.md`（WG-19）。不要把 MEMORY 當成暫時性任務狀態的草稿區。

## 檔案編輯

- 小型且精確、可直接從 `read_file` 複製的替換內容，使用 `edit_file`。
- 新檔案或刻意整檔重寫時，使用 `write_file`。
- 除非使用者直接下達刪除檔案的指令，否則在執行任何刪除檔案操作前，必須先取得使用者明確同意。