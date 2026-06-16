依下方 Analysis Result 更新記憶檔。

- `[FILE]`：加入對應檔案
- `[FILE-REMOVE]`：從記憶檔刪除對應內容
- `[SKILL]`：用 write_file 建立 `skills/<name>/SKILL.md`

## 檔案路徑（相對 workspace 根目錄）

- SOUL.md
- USER.md
- memory/MEMORY.md
- skills/<name>/SKILL.md（僅 [SKILL]）

## 編輯規則

- 下方已提供 Current Files 全文，原則上不必 read_file
- old_text 須精確匹配（含周圍空行以確保唯一）
- 同一檔案多處修改可合併一次 edit_file
- 刪除：以 section + bullets 為 old_text，new_text 留空
- 只做 surgical edit，禁止整檔覆寫
- 若無需更新，不要呼叫工具
- 不要把一次性測試、遊戲互動、臨時指令、角色扮演或單次任務要求寫入 USER/SOUL；若 Analysis Result 仍包含這類內容，直接忽略
- USER/SOUL 只接受長期、跨任務仍有用、可泛化的偏好，例如語言、回覆風格、常用工具、長期工作流程偏好

## Skill 建立（[SKILL]）

- 用 write_file 建立 skills/<name>/SKILL.md
- 先 read_file `{{ skill_creator_path }}` 參考格式
- **Dedup**：read 下方 Existing Skills，若已有相同 workflow 則跳過
- YAML frontmatter 含 name、description
- SKILL.md 控制在 2000 字以內
- 含：何時使用、步驟、輸出格式、至少一個範例
- 不覆寫既有 skill 目錄

## 品質

- 每行 bullet 須有獨立價值
- 不確定是否刪除時保留並加 `(verify currency)`
