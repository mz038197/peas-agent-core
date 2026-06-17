"""Parse LangChain AIMessage / chunk content for Responses API streaming."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

StreamKind = Literal["reasoning", "text"]


def _reasoning_text_from_block(block: dict[str, Any]) -> str:
    reasoning = block.get("reasoning")
    if isinstance(reasoning, str) and reasoning:
        return reasoning
    summary = block.get("summary")
    if isinstance(summary, str) and summary:
        return summary
    if isinstance(summary, list):
        parts: list[str] = []
        for item in summary:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
            elif isinstance(item, str) and item:
                parts.append(item)
        return "".join(parts)
    return ""


def _text_from_block(block: dict[str, Any]) -> str:
    text = block.get("text")
    return text if isinstance(text, str) else ""


def iter_content_blocks(message: BaseMessage | AIMessageChunk) -> Iterable[dict[str, Any]]:
    blocks = getattr(message, "content_blocks", None)
    if blocks:
        for block in blocks:
            if isinstance(block, dict):
                yield block
        return

    content = message.content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                yield block


def iter_chunk_deltas(chunk: AIMessageChunk) -> Iterable[tuple[StreamKind, str]]:
    """Yield incremental (kind, text) pairs from a streaming chunk."""
    saw_blocks = False
    for block in iter_content_blocks(chunk):
        saw_blocks = True
        block_type = block.get("type")
        if block_type == "reasoning":
            text = _reasoning_text_from_block(block)
            if text:
                yield "reasoning", text
        elif block_type == "text":
            text = _text_from_block(block)
            if text:
                yield "text", text

    if saw_blocks:
        return

    content = chunk.content
    if isinstance(content, str) and content:
        yield "text", content


def extract_answer_text(message: BaseMessage) -> str:
    """Return user-visible answer text, excluding reasoning blocks."""
    if not isinstance(message, AIMessage):
        content = message.content
        return content.strip() if isinstance(content, str) else str(content).strip()

    parts: list[str] = []
    saw_blocks = False
    for block in iter_content_blocks(message):
        saw_blocks = True
        if block.get("type") == "text":
            text = _text_from_block(block)
            if text:
                parts.append(text)

    if saw_blocks:
        return "".join(parts).strip()

    content = message.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = _text_from_block(block)
                if text:
                    parts.append(text)
        return "".join(parts).strip()
    return str(content).strip()


def estimate_ai_message_text_length(message: AIMessage) -> int:
    text = extract_answer_text(message)
    if text:
        return len(text)
    tc = message.tool_calls or []
    if tc:
        return 32 * len(tc)
    return 0
