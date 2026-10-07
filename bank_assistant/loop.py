import asyncio
import os

from google.genai import types
from pydantic import BaseModel, Field

from google.adk import Agent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.integrations.openai import OpenAILlm
from google.adk.runners import Runner

# adk web 不會載這支。要試 LOOP 用：uv run python bank_assistant/loop.py
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

_REPORT_FIELDS = {
    "case_name": "案名",
    "application": "申請內容",
    "customer": "主檔",
    "limit": "既有額度",
    "watchlist": "警示",
    "registry": "變更登記",
    "missing_docs": "缺件",
    "basis": "依據",
    "suggestion": "建議",
}


class IntakeSlip(BaseModel):
    company: str = Field(description="公司名稱。聽不出來就填公司不明")
    amount_wan: str = Field(description="申請金額，單位是萬。沒有就填無")
    question: str = Field(description="經辦要問的事")


class ReviewReport(BaseModel):
    case_name: str = Field(description="案名")
    application: str = Field(description="申請內容，含申請金額")
    customer: str = Field(description="主檔，只寫查詢回傳")
    limit: str = Field(description="既有額度。不准寫申請金額")
    watchlist: str = Field(description="警示，只寫查詢回傳")
    registry: str = Field(description="變更登記，只寫查詢回傳")
    missing_docs: str = Field(description="缺件。沒有就填無")
    basis: str = Field(description="依據，只寫查詢回傳。不准寫條號")
    suggestion: str = Field(description="建議。這一節填還沒選路")


def _copy_intake_fields(callback_context) -> None:
    intake = callback_context.state.get("intake")
    if not isinstance(intake, dict):
        return None
    for key in ("company", "amount_wan", "question"):
        callback_context.state[key] = intake.get(key) or ""
    return None


def _report_faults(report, amount_wan: str) -> list[str]:
    if not isinstance(report, dict):
        return ["報告不是規定的格式"]
    faults = []
    for key, label in _REPORT_FIELDS.items():
        if not str(report.get(key) or "").strip():
            faults.append(f"{label}是空的")
    limit = str(report.get("limit") or "")
    amount = str(amount_wan or "").strip()
    if amount and amount not in {"無", ""} and amount in limit:
        faults.append("額度寫成申請金額")
    if "條" in str(report.get("basis") or ""):
        faults.append("依據寫了條號")
    return faults


def _check_report(callback_context) -> None:
    faults = _report_faults(
        callback_context.state.get("report"),
        str(callback_context.state.get("amount_wan") or ""),
    )
    callback_context.state["faults"] = "；".join(faults)
    if not faults:
        callback_context.actions.escalate = True
    return None


def _query_agent(name: str, tool, output_key: str, what: str) -> Agent:
    return Agent(
        name=name,
        model=_model,
        instruction=(
            f"你只查 {{company}} 的{what}。只呼叫 {tool.__name__}。"
            "最後只寫工具回傳。不准寫報告，不准核貸。"
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
        "你只聽經辦這句話。不准查資料，不准寫報告，不准核貸。"
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
report_agent = Agent(
    name="report",
    model=_model,
    instruction=(
        "你寫初審報告。不准再查，不准核貸，不准送審，不准補查詢裡沒有的數字。\n"
        "收件：{intake}\n"
        "主檔：{customer}\n"
        "既有額度：{exposure}\n"
        "警示：{watchlist}\n"
        "變更登記：{registry}\n"
        "上次沒過：{faults?}\n"
        "上次有列出缺點，就只改那些。申請金額寫在申請內容，不准寫進既有額度。"
        "依據不准寫條號。建議填還沒選路。"
    ),
    output_schema=ReviewReport,
    output_key="report",
    after_agent_callback=_check_report,
    generate_content_config=_zero,
)
revise_agent = LoopAgent(
    name="revise",
    max_iterations=2,
    sub_agents=[report_agent],
)
handback_agent = Agent(
    name="handback",
    model=_model,
    instruction=(
        "你把初審報告交給人。不准再改，不准再查，不准核貸，不准送審。\n"
        "缺點：{faults?}\n"
        "報告：{report}\n"
        "沒有缺點，就說初審報告合格，並照報告的段落講出來。"
        "有缺點，就說兩輪後仍不合格，列出缺點，把這份報告留下。"
    ),
    output_key="handback",
    generate_content_config=_zero,
)
root_agent = SequentialAgent(
    name="bank_assistant",
    sub_agents=[intake_agent, query_agent, revise_agent, handback_agent],
)


def _check_loop() -> None:
    good = {key: "有" for key in _REPORT_FIELDS}
    good["limit"] = "300"
    good["basis"] = "警示無"
    assert _report_faults(good, "800") == []
    bad = dict(good)
    bad["limit"] = "800"
    bad["basis"] = "依第3條"
    bad["case_name"] = ""
    faults = _report_faults(bad, "800")
    assert "額度寫成申請金額" in faults
    assert "依據寫了條號" in faults
    assert "案名是空的" in faults
    assert revise_agent.max_iterations == 2
    assert [agent.name for agent in root_agent.sub_agents] == [
        "intake",
        "queries",
        "revise",
        "handback",
    ]


_check_loop()


async def _chat() -> None:
    runner = Runner(
        app_name="bank_assistant",
        agent=root_agent,
        session_service=_session_service(),
    )
    print("LOOP：收件、同時查、初審報告最多改兩輪。輸入一句話。空白行結束。")
    while True:
        text = input("> ")
        if not text.strip():
            break
        await runner.run_debug(text, session_id="loop")


if __name__ == "__main__":
    asyncio.run(_chat())
