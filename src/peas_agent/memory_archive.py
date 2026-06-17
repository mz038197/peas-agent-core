"""Session archive helpers: Consolidator and cross-session history writes."""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI

from peas_agent.llm_content import extract_answer_text
from peas_agent.memory_store import MemoryStore

MAX_ARCHIVE_CHUNK_MESSAGES = 60
CONSOLIDATION_MAX_RETRIES = 3
CONSOLIDATOR_ARCHIVE_PROMPT = (
    Path(__file__).resolve().parent / "prompts" / "consolidator_archive.md"
)


def chunk_to_text(chunk: list[BaseMessage], message_plaintext) -> str:
    return "\n".join(message_plaintext(m) for m in chunk)


def pick_archive_end(
    messages: list[BaseMessage],
    start: int,
    *,
    max_messages: int = MAX_ARCHIVE_CHUNK_MESSAGES,
) -> int:
    """Return end index (exclusive) for the next archive chunk."""
    if start >= len(messages):
        return start

    end = min(start + max_messages, len(messages))
    if end >= len(messages):
        return end

    for idx in range(end - 1, start - 1, -1):
        if isinstance(messages[idx], HumanMessage):
            return idx if idx > start else start + 1
    return end


def invoke_archive_summary(consolidation_llm: ChatOpenAI, chunk_text: str) -> str | None:
    from langchain_core.messages import HumanMessage as HM, SystemMessage

    system = CONSOLIDATOR_ARCHIVE_PROMPT.read_text(encoding="utf-8")
    response = consolidation_llm.invoke(
        [
            SystemMessage(content=system),
            HM(content=chunk_text),
        ]
    )
    summary = extract_answer_text(response).strip()
    if not summary or summary.lower() == "(nothing)":
        return None
    return summary


def archive_session_chunk(
    consolidation_llm: ChatOpenAI,
    store: MemoryStore,
    chunk: list[BaseMessage],
    session_key: str,
    *,
    message_plaintext,
) -> bool:
    """Summarize chunk and append to history.jsonl. Returns True on success."""
    if not chunk:
        return False

    chunk_text = chunk_to_text(chunk, message_plaintext)
    for _ in range(CONSOLIDATION_MAX_RETRIES):
        try:
            summary = invoke_archive_summary(consolidation_llm, chunk_text)
        except Exception:
            continue
        if summary:
            store.append_history(summary, session_key=session_key)
            return True

    fail_note = " ".join(chunk_text.split())[:200]
    store.append_history(
        f"[CONSOLIDATION-FAILED] {fail_note}",
        session_key=session_key,
    )
    return False


def cross_session_archive(
    workspace: Path,
    active_session_path: str,
    consolidation_llm: ChatOpenAI,
    store: MemoryStore,
    *,
    load_session_jsonl,
    save_session_jsonl,
    message_plaintext,
) -> int:
    """Archive pending content from other sessions. Returns chunks archived."""
    sessions_dir = workspace / "sessions"
    if not sessions_dir.is_dir():
        return 0

    active: Path | None = None
    if active_session_path:
        active = Path(active_session_path).resolve()

    archived = 0

    for path in sorted(sessions_dir.glob("*.jsonl")):
        if active is not None and path.resolve() == active:
            continue

        history, meta = load_session_jsonl(str(path))
        if not history:
            continue

        last = int(meta.get("last_consolidated", 0) or 0) if meta else 0
        while last < len(history):
            end = pick_archive_end(history, last)
            if end <= last:
                break

            chunk = history[last:end]
            archive_session_chunk(
                consolidation_llm,
                store,
                chunk,
                path.name,
                message_plaintext=message_plaintext,
            )
            last = end
            save_session_jsonl(str(path), history, meta, last)
            archived += 1

    return archived
