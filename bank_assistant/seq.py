import asyncio
import os

from google.genai import types

from google.adk import Agent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.integrations.openai import OpenAILlm
from google.adk.runners import Runner

# adk web 不會載這支。要試 SEQ 用：uv run python bank_assistant/seq.py
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

# SEQ：先查完，再寫意見。寫意見的那顆沒有工具。
lookup_agent = Agent(
    name="lookup",
    model=_model,
    instruction=(
        "你只負責查。四支都要呼叫：get_customer、get_exposure、"
        "check_watchlist、get_registry。"
        "最後用一段話寫下主檔、額度、警示、變更登記，只能寫工具回傳。"
        "不准寫意見，不准核貸。"
    ),
    tools=[get_customer, get_exposure, check_watchlist, get_registry],
    output_key="lookup",
    generate_content_config=_zero,
)
memo_agent = Agent(
    name="memo",
    model=_model,
    instruction=(
        "你只根據下面的查詢結果寫意見。不准再查，不准核貸，不准補結果裡沒有的數字。\n"
        "{lookup}\n"
        "五欄都要有：客戶、額度、依據、缺件、建議路徑。"
        "依據只寫查詢回傳了什麼，不准寫條號。"
        "查詢結果是空的，就說還沒查完，不要寫意見。"
    ),
    output_key="memo",
    generate_content_config=_zero,
)
root_agent = SequentialAgent(
    name="bank_assistant",
    sub_agents=[lookup_agent, memo_agent],
)


def _check_seq() -> None:
    assert [agent.name for agent in root_agent.sub_agents] == ["lookup", "memo"]
    assert lookup_agent.output_key == "lookup"
    assert memo_agent.output_key == "memo"
    assert memo_agent.tools == []
    assert "{lookup}" in memo_agent.instruction
    assert "300" not in lookup_agent.instruction
    assert "300" not in memo_agent.instruction


_check_seq()


async def _chat() -> None:
    runner = Runner(
        app_name="bank_assistant",
        agent=root_agent,
        session_service=_session_service(),
    )
    print("SEQ：先查再寫意見。輸入一句話。空白行結束。")
    while True:
        text = input("> ")
        if not text.strip():
            break
        await runner.run_debug(text, session_id="s1")


if __name__ == "__main__":
    asyncio.run(_chat())
