import asyncio
import os

from google.genai import types
from pydantic import BaseModel, Field

from google.adk import Agent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.integrations.openai import OpenAILlm
from google.adk.runners import Runner

# adk web 不會載這支。要試 PAR 用：uv run python bank_assistant/par.py
try:
    from .agent import _load_env, _session_service
    from .queries import check_watchlist, get_customer, get_exposure, get_registry
except ImportError:
    from agent import _load_env, _session_service
    from queries import check_watchlist, get_customer, get_exposure, get_registry

_load_env()

_model = OpenAILlm(
    model=os.environ["MODEL_NAME"],
    base_url=os.environ["BASE_URL"],
    api_key=os.environ["VCR_API_KEY"],
)
_zero = types.GenerateContentConfig(temperature=0)


class IntakeSlip(BaseModel):
    company: str = Field(description="公司名稱。聽不出來就填公司不明")
    amount_wan: str = Field(description="申請金額，單位是萬。沒有就填無")
    question: str = Field(description="經辦要問的事")


def _copy_intake_fields(callback_context) -> None:
    intake = callback_context.state.get("intake")
    if not isinstance(intake, dict):
        return None
    for key in ("company", "amount_wan", "question"):
        callback_context.state[key] = intake.get(key) or ""
    return None


def _query_agent(name: str, tool, output_key: str, what: str) -> Agent:
    return Agent(
        name=name,
        model=_model,
        instruction=(
            f"你只查 {{company}} 的{what}。只呼叫 {tool.__name__}。"
            "最後只寫工具回傳。不准寫意見，不准核貸。"
            "申請金額不是既有額度。"
            "公司是公司不明，或公司是空的，就說先補公司，不要查。"
        ),
        tools=[tool],
        output_key=output_key,
        generate_content_config=_zero,
    )


intake_agent = Agent(
    name="intake",
    model=_model,
    instruction=(
        "你只聽經辦這句話。不准查資料，不准寫意見，不准核貸。"
        "最後交一份收件。聽不出公司，公司填公司不明，不要猜。"
    ),
    output_schema=IntakeSlip,
    output_key="intake",
    after_agent_callback=_copy_intake_fields,
    generate_content_config=_zero,
)
customer_agent = _query_agent("customer", get_customer, "customer", "主檔")
exposure_agent = _query_agent("exposure", get_exposure, "exposure", "既有額度")
watchlist_agent = _query_agent("watchlist", check_watchlist, "watchlist", "警示")
registry_agent = _query_agent("registry", get_registry, "registry", "變更登記")
query_agent = ParallelAgent(
    name="queries",
    sub_agents=[customer_agent, exposure_agent, watchlist_agent, registry_agent],
)
memo_agent = Agent(
    name="memo",
    model=_model,
    instruction=(
        "你只根據收件和四格查詢寫意見。不准再查，不准核貸，不准補結果裡沒有的數字。\n"
        "收件：{intake}\n"
        "主檔：{customer}\n"
        "既有額度：{exposure}\n"
        "警示：{watchlist}\n"
        "變更登記：{registry}\n"
        "五欄都要有：客戶、額度、依據、缺件、建議路徑。"
        "額度寫既有額度。申請金額另寫，不能混進額度。"
        "依據只寫查詢回傳了什麼，不准寫條號。"
        "任何一格是空的，或寫著還沒查，就說還沒查完，不要寫意見。"
    ),
    output_key="memo",
    generate_content_config=_zero,
)
root_agent = SequentialAgent(
    name="bank_assistant",
    sub_agents=[intake_agent, query_agent, memo_agent],
)


def _check_par() -> None:
    assert [agent.name for agent in root_agent.sub_agents] == [
        "intake",
        "queries",
        "memo",
    ]
    keys = [agent.output_key for agent in query_agent.sub_agents]
    assert keys == ["customer", "exposure", "watchlist", "registry"]
    assert all(len(agent.tools) == 1 for agent in query_agent.sub_agents)
    assert memo_agent.tools == []
    assert "{customer}" in memo_agent.instruction


_check_par()


async def _chat() -> None:
    runner = Runner(
        app_name="bank_assistant",
        agent=root_agent,
        session_service=_session_service(),
    )
    print("PAR：收件後四支一起查，再寫意見。輸入一句話。空白行結束。")
    while True:
        text = input("> ")
        if not text.strip():
            break
        await runner.run_debug(text, session_id="par")


if __name__ == "__main__":
    asyncio.run(_chat())
