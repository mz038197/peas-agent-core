"""Template-based memory summary for human-readable SUMMARY.md."""

from __future__ import annotations

from peas_agent.memory_store import MemoryStore


def regenerate_memory_summary(store: MemoryStore) -> str:
    """Build SUMMARY.md from MEMORY/SOUL/USER without LLM."""
    sections: list[str] = ["# 記憶摘要\n", "_此檔僅供人類閱讀，不進 agent prompt。_\n"]

    user = store.read_user().strip()
    if user:
        sections.append("## 關於你\n")
        sections.append(_bullets_from_markdown(user))

    soul = store.read_soul().strip()
    if soul:
        sections.append("\n## Agent 風格\n")
        sections.append(_bullets_from_markdown(soul))

    memory = store.read_memory().strip()
    if memory:
        sections.append("\n## 長期記憶\n")
        sections.append(_bullets_from_markdown(memory))

    if len(sections) <= 2:
        sections.append("\n（尚無記憶內容）\n")

    text = "\n".join(sections).strip() + "\n"
    store.summary_file.write_text(text, encoding="utf-8")
    return text


def _bullets_from_markdown(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            lines.append(line)
        elif line.startswith("* "):
            lines.append("- " + line[2:])
        else:
            lines.append(f"- {line}")
    return "\n".join(lines) if lines else "- （空）\n"
