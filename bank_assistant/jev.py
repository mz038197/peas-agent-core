"""Jev 選部門，再啟動對應的 sub_agent。

決策打 Vans router 的 POST /v1/decisions，不是聊天，也不包成 tool。
BASE_URL 已含 /v1。模型預設 vcr-auto，要指定 Jev 時設 DECISION_MODEL=openrouter@typesafe/jev-1.13。
"""

import asyncio
import os

import httpx
from google.genai import types

from google.adk import Agent
from google.adk.agents.base_agent import BaseAgent
from google.adk.events.event import Event
from google.adk.integrations.openai import OpenAILlm
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

try:
    from .agent import _load_env
except ImportError:
    from agent import _load_env

_load_env()

_model = OpenAILlm(
    model=os.environ["MODEL_NAME"],
    base_url=os.environ["BASE_URL"],
    api_key=os.environ["VCR_API_KEY"],
)
_zero = types.GenerateContentConfig(temperature=0)

DESKS = ("review", "supplement", "draft")


def _desk(name: str, title: str) -> Agent:
    return Agent(
        name=name,
        model=_model,
        description=title,
        instruction=(
            f"你是{title}。只收這份初審報告，寫三行：部門、案名、為什麼送到這裡。\n"
            "報告：{report}\n"
            "不准重寫整份報告，不准核貸，不准送審。"
        ),
        generate_content_config=_zero,
    )


def _desk_from_answer(body: dict) -> tuple[str, dict]:
    answer = (body.get("answers") or {}).get("desk")
    if not isinstance(answer, dict):
        raise RuntimeError(f"決策沒有 desk：{body.get('answers')}")
    for key in ("choice", "selected", "answer", "label"):
        value = answer.get(key)
        if value in DESKS:
            return value, answer
    probs = answer.get("probabilities") or answer.get("distribution") or {}
    if isinstance(probs, dict) and probs:
        best = max(probs, key=probs.get)
        if best in DESKS:
            return best, answer
    raise RuntimeError(f"決策沒有回部門：{answer}")


async def _ask_jev(report: dict) -> tuple[str, dict]:
    base = os.environ["BASE_URL"].rstrip("/")
    payload = {
        "model": os.environ.get("DECISION_MODEL", "vcr-auto"),
        "state": report,
        "questions": {
            "desk": {
                "type": "choice",
                "instructions": "這份初審報告送到哪個部門？警示命中選 review。缺件不是無、且警示不是命中，選 supplement。兩個都有選 review。其餘選 draft。",
                "criteria": {
                    "review": "警示是命中",
                    "supplement": "缺件不是無，且警示不是命中",
                    "draft": "其餘，留在經辦草稿櫃",
                },
            }
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{base}/decisions",
            headers={"Authorization": f"Bearer {os.environ['VCR_API_KEY']}"},
            json=payload,
        )
    if response.status_code != 200:
        raise RuntimeError(f"決策失敗 {response.status_code}：{response.text[:400]}")
    return _desk_from_answer(response.json())


class JevRoute(BaseAgent):
    async def _run_async_impl(self, ctx):
        faults = str(ctx.session.state.get("faults") or "").strip()
        if faults:
            yield _text_event(ctx, self.name, f"報告未合格，留在經辦。{faults}")
            return
        report = ctx.session.state.get("report")
        if not isinstance(report, dict):
            yield _text_event(ctx, self.name, "沒有初審報告，不送部門。")
            return
        desk, answer = await _ask_jev(report)
        yield _text_event(ctx, self.name, f"Jev 選了 {desk}。{answer}")
        child = next(agent for agent in self.sub_agents if agent.name == desk)
        async for event in child.run_async(ctx):
            yield event


def _text_event(ctx, author: str, text: str) -> Event:
    return Event(
        invocation_id=ctx.invocation_id,
        author=author,
        branch=ctx.branch,
        content=types.Content(role="model", parts=[types.Part(text=text)]),
    )


review_agent = _desk("review", "覆核部門")
supplement_agent = _desk("supplement", "補件部門")
draft_agent = _desk("draft", "草稿櫃")
root_agent = JevRoute(
    name="route",
    sub_agents=[review_agent, supplement_agent, draft_agent],
)


def _check_jev() -> None:
    desk, _answer = _desk_from_answer(
        {
            "answers": {
                "desk": {
                    "type": "choice",
                    "choice": "review",
                    "probabilities": {"review": 0.9, "draft": 0.1},
                }
            }
        }
    )
    assert desk == "review"
    assert [agent.name for agent in root_agent.sub_agents] == list(DESKS)


_check_jev()

_SAMPLE = {
    "case_name": "山海貿易",
    "application": "週轉金 800 萬",
    "customer": "主檔在",
    "limit": "無紀錄",
    "watchlist": "命中",
    "registry": "無近期變更",
    "missing_docs": "無",
    "basis": "警示命中",
    "suggestion": "還沒選路",
}


async def _demo() -> None:
    service = InMemorySessionService()
    await service.create_session(
        app_name="bank_assistant", user_id="u", session_id="jev"
    )
    runner = Runner(
        app_name="bank_assistant",
        agent=root_agent,
        session_service=service,
    )
    message = types.Content(role="user", parts=[types.Part(text="送出合格的初審報告")])
    async for event in runner.run_async(
        user_id="u",
        session_id="jev",
        new_message=message,
        state_delta={"report": _SAMPLE, "faults": ""},
    ):
        if event.content and event.content.parts:
            text = "".join(part.text or "" for part in event.content.parts)
            if text:
                print(text)


if __name__ == "__main__":
    asyncio.run(_demo())
