"""Dream and chat LLM clients must be independent instances."""

from __future__ import annotations

from peas_agent.core import _build_dream_llm, _build_llm


def test_dream_llm_is_separate_instance() -> None:
    config = {
        "llm": {
            "api_key": "test-key",
            "model": "gpt-test",
            "temperature": 0.1,
            "request_timeout": 30,
        },
        "dream": {"model": None},
    }
    chat_llm = _build_llm(config)
    dream_llm = _build_dream_llm(config)
    assert chat_llm is not dream_llm
