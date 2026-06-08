# 代理人指令

## 工作區指引

將這個檔案用於記錄此工作區的專案偏好、重複性的工作流程慣例，以及希望代理人記住的指示。請將關於使用者的長期且穩定事實放在 `USER.md`，將個性與行為放在 `SOUL.md`，將長期記憶放在 `memory/MEMORY.md`。

## 工作坊慣例

- 這個專案使用 **uv** 管理 Python 相依套件。請在專案根目錄使用 `exec uv add <package>` 安裝套件，不要使用 `pip install`。
- 對於可重複執行的任務，優先使用 `write_file` 建立 `.py` 腳本，再用 `exec uv run python <相對路徑>` 執行。
- 自訂 skill 放在 `skills/<name>/SKILL.md`。在遵循某個 skill 之前，先用 `read_file` 載入它。
- 長期事實會在上下文預算管理期間自動彙整到 `memory/MEMORY.md`（WG-19）。不要把 MEMORY 當成暫時性任務狀態的草稿區。

## 檔案編輯

- 小型且精確、可直接從 `read_file` 複製的替換內容，使用 `edit_file`。
- 新檔案或刻意整檔重寫時，使用 `write_file`。
- 除非使用者直接下達刪除檔案的指令，否則在執行任何刪除檔案操作前，必須先取得使用者明確同意。