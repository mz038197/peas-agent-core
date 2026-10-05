import asyncio
import os
from pathlib import Path

from google.genai import types

from google.adk import Agent
from google.adk.integrations.openai import OpenAILlm
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.sessions.sqlite_session_service import SqliteSessionService

# adk web 把這個資料夾當套件載入。直接跑 agent.py 時沒有套件，改從同目錄找。
try:
    from .queries import check_watchlist, get_customer, get_exposure, get_registry
except ImportError:
    from queries import check_watchlist, get_customer, get_exposure, get_registry


def _load_env() -> None:
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


# 直接跑 agent.py 時，ADK 不會先讀 .env。建立 agent 前要自己載。
_load_env()

# 第 3 節：四支查詢在 queries.py。退回上一節時，tools 拿掉，指令改回「不准講額度」。
root_agent = Agent(
    name="bank_assistant",
    model=OpenAILlm(
        model=os.environ["MODEL_NAME"],
        base_url=os.environ["BASE_URL"],
        api_key=os.environ["VCR_API_KEY"],
    ),
    instruction=(
        "你是嚴格的授信初審。資料不足就說還要查。不准核貸。"
        "問客戶呼叫 get_customer，問額度呼叫 get_exposure，"
        "問警示呼叫 check_watchlist，問變更登記呼叫 get_registry。"
        "沒呼叫不准講額度、警示、變更。"
        "新的一輪不能用上一輪對話裡的數字，要再查一次。"
    ),
    tools=[get_customer, get_exposure, check_watchlist, get_registry],
    generate_content_config=types.GenerateContentConfig(temperature=0),
)


# def _check_cases() -> None:
#     assert "300" not in root_agent.instruction
#     assert root_agent.model.model == "ollama_cloud@minimax-m3:cloud"
#     assert root_agent.model.base_url == "https://ai.vanscoding.com/v1"
#     names = {tool.__name__ for tool in root_agent.tools}
#     assert names == {
#         "get_customer",
#         "get_exposure",
#         "check_watchlist",
#         "get_registry",
#     }


# _check_cases()


def _session_service():
    # SESSION_STORE=sqlite（預設）| memory | postgres
    store = os.environ.get("SESSION_STORE", "sqlite")
    if store == "memory":
        print("對話只放記憶體。程式關掉就沒了。")
        return InMemorySessionService()
    if store == "postgres":
        from google.adk.sessions.database_session_service import DatabaseSessionService

        print("對話寫入雲端 PostgreSQL。編號 s1。")
        return DatabaseSessionService(os.environ["SESSION_DB_URL"])
    db_path = Path(__file__).resolve().parent / ".adk" / "session.db"
    db_path.parent.mkdir(exist_ok=True)
    print(f"對話寫入 {db_path}。編號 s1。")
    return SqliteSessionService(str(db_path))


async def _chat() -> None:
    _load_env()
    runner = Runner(
        app_name="bank_assistant",
        agent=root_agent,
        session_service=_session_service(),
    )
    print("輸入一句話。空白行結束。")
    while True:
        text = input("> ")
        if not text.strip():
            break
        await runner.run_debug(text, session_id="s1")


if __name__ == "__main__":
    asyncio.run(_chat())
