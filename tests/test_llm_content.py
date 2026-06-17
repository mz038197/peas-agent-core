"""Tests for Responses API content parsing helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk

from peas_agent.llm_content import (
    extract_answer_text,
    iter_chunk_deltas,
)


def test_iter_chunk_deltas_reasoning_and_text() -> None:
    chunk = AIMessageChunk(
        content=[
            {
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": "think"}],
            },
            {"type": "text", "text": "hi"},
        ]
    )
    assert list(iter_chunk_deltas(chunk)) == [("reasoning", "think"), ("text", "hi")]


def test_iter_chunk_deltas_string_content() -> None:
    chunk = AIMessageChunk(content="plain")
    assert list(iter_chunk_deltas(chunk)) == [("text", "plain")]


def test_extract_answer_text_strips_reasoning() -> None:
    message = AIMessage(
        content=[
            {"type": "reasoning", "reasoning": "hidden"},
            {"type": "text", "text": "visible"},
        ]
    )
    assert extract_answer_text(message) == "visible"


def test_extract_answer_text_plain_string() -> None:
    assert extract_answer_text(AIMessage(content="ok")) == "ok"


def test_iter_chunk_deltas_content_blocks_property() -> None:
    chunk = SimpleNamespace(
        content=[],
        content_blocks=[
            {"type": "reasoning", "reasoning": "abc"},
            {"type": "text", "text": "xyz"},
        ],
    )
    assert list(iter_chunk_deltas(chunk)) == [("reasoning", "abc"), ("text", "xyz")]
