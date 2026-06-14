---
name: skill-creator
description: SKILL.md 格式參考——供 Dream 建立新 skill 時使用
---

# Skill 建立格式

## Frontmatter（必填）

```yaml
---
name: kebab-case-name
description: 一句話說明何時觸發此 skill
---
```

## 正文結構

1. **何時使用** — 觸發條件與關鍵字
2. **步驟** —  numbered 或可勾選清單
3. **輸出格式** — agent 應產出什麼
4. **範例** — 至少一個具體例子

## 命名

- 目錄名 = frontmatter `name` = kebab-case
- 路徑：`skills/<name>/SKILL.md`

## 限制

- 指令集，非程式碼庫
- 引用 agent 可用工具（read_file、edit_file、exec 等）
- 繁中或英文皆可，與 workspace 一致
