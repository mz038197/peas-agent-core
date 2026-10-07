# 金融業 Google ADK 工作坊：12 小時

格式對齊升級版大綱。同一天的節數往下累加。

| 日期 | 節數 | 時間 | 教學主題 | 教學內容 | 教學工具 |
|---|---|---|---|---|---|
| 第一天<br>第1堂 | 第1節 | 09:00 – 09:50 | 建立 Agent 並寫入兩套身份<br>(同一份 agent.py) | 安裝 google-adk<br>.env 放 `VCR_API_KEY`、`MODEL_NAME=vcr-auto`、`BASE_URL=https://ai.vanscoding.com/v1`<br>`root_agent` 的 model 用 `OpenAILlm`，三個值從這三個環境變數讀<br>`_load_env()` 放在建立 `root_agent` 之前。直接跑 `agent.py` 時 ADK 不會先載 `.env`<br>建立 root_agent，temperature=0，指令先寫嚴格初審<br>三種執行都要跑過：`uv run adk web bank_assistant --port 8010`<br>`uv run adk run bank_assistant`<br>`uv run python bank_assistant/agent.py`<br>問「800 萬能不能做」，要說還要查<br>同一畫面再問，要答出禾豐食品<br>同一份檔把指令改成衝業績，新對話同一句，答案要分開<br>不准講既有額度 300 萬。講得出就是編的 | 講義<br>Google ADK（adk web / adk run / agent.py） |
| 第一天<br>第1堂 | 第2節 | 10:00 – 11:00 | Lv5 Memory<br>(訊息串不是案件檔) | 同一輪問「我剛問了哪一家」，要答得出<br>新開一輪再問，要答不出<br>執行 `uv run python bank_assistant/agent.py`。`run_debug` 把這句送出<br>預設寫入 `.adk/session.db`，編號 s1。關掉再執行，同一則還在<br>換 `session_id` 才是新的一輪。舊編號仍留在資料庫<br>`SESSION_STORE=memory` 關掉就沒了。`postgres` 用 `postgresql+asyncpg://`，先 `uv add asyncpg`<br>正式環境不靠 `input()` 和 `run_debug`。留下 `root_agent`，對話寫進資料庫<br>這一節不掛工具 | 講義<br>Google ADK |
| 第一天<br>第2堂 | 第3節 | 11:10 – 12:05 | ReAct<br>(同一圈的前半：投影片與禾豐) | ADK 沒有 ReAct 類別。掛上 tools 後，Runner 會一直叫模型<br>回傳有函式呼叫，ADK 跑 Python，把結果送回，再叫一次模型<br>回傳只剩一段話，這一圈才停。這個迴圈不用寫<br>投影片對 adk web 的事件：決定呼叫、呼叫、回傳、講給人聽<br>四支查詢寫在 queries.py：get_customer、get_exposure、check_watchlist、get_registry<br>agent.py 的 tools 直接掛這四個普通函式。不用 LangChain 的 @tool<br>300 萬只寫在 queries.py。instruction 出現 300，當沒過<br>問禾豐額度，畫面上要有 get_exposure，答案是 300 萬<br>沒有工具呼叫卻講出 300 萬，當沒過<br>公司名稱對不上，或同時對上兩家，不猜、不帶出額度<br>這一節不開 planner，不掛 peas-agent-tools<br>退回上一節要把 tools 拿掉，指令改回「不准講額度」 | 講義<br>Google ADK<br>queries.py<br>投影片 |
| 第一天<br>第2堂 | 第4節 | 12:15 – 13:10 | ReAct<br>(同一圈的後半：山海) | 不再講一套新機制。同一圈換山海貿易<br>畫面上要有 check_watchlist，回傳是命中<br>把禾豐的無警示、300 萬、財簽齊套到山海，當沒過<br>沒看完回傳就寫結論，當沒過<br>山海沒有額度、沒有財簽。get_exposure 是無紀錄，不准補數字<br>ADK 不擋「沒查就講」。沒過是人眼看畫面上沒有那筆工具紀錄<br>仍不准核貸。不寫分流、不存草稿、不開 planner | 講義<br>Google ADK<br>queries.py |
| 第一天<br>第3堂 | 第5節 | 14:10 – 15:05 | Prompt Chaining / Parallelization<br>(SEQ / PAR) | Sequential 寫在 seq.py，不改 agent.py。三步：收件、查詢、寫意見<br>收件不掛工具。output_schema 用 IntakeSlip，三欄 company、amount_wan、question<br>最後一段寫進 output_key intake。callback 把 company 抄到 state["company"]<br>查詢用 {company} 決定查哪一家，四支都要叫，結果寫進 lookup<br>{intake.company} 不會拆欄。規格要寫明欄位名和型別，不能只傳一串名字<br>意見沒有工具，讀 {intake} 和 {lookup}<br>申請 800 萬和既有額度 300 萬要分開。查詢是空的就說還沒查完<br>試跑 `uv run python bank_assistant/seq.py`<br>Parallel 寫在 par.py，接同一句收件。中間改成四顆同時查：主檔、額度、警示、變更登記<br>各掛一支工具，各寫 customer、exposure、watchlist、registry。不能寫進同一個 key<br>意見改讀這四格加收件。少一格就說還沒查完<br>試跑 `uv run python bank_assistant/par.py`，對話編號 par<br>每步結果寫進 Output Key，下一步要讀得到 | 講義<br>Google ADK<br>seq.py<br>par.py |
| 第一天<br>第3堂 | 第6節 | 15:15 – 16:10 | LOOP／RTR<br>(改到齊，再換路) | Loop 寫在 loop.py。接同一句收件，四支仍同時查，查詢不重跑<br>最後寫初審報告。段落：案名、申請內容、主檔、既有額度、警示、變更登記、缺件、依據、建議<br>output_schema 用 ReviewReport，寫進 report<br>Python 檢查：額度裡出現申請金額、依據有條號、有段落是空的，就再寫<br>合格就停。最多兩輪<br>兩輪後仍不合格，handback 列出缺點，把報告留給人。不准再改、不准核貸、不准送審<br>試跑 `uv run python bank_assistant/loop.py`，對話編號 loop<br>RTR 接在這份報告後面。有缺點留在經辦，不送部門<br>部門都是 sub_agents：review 覆核、supplement 補件、draft 草稿。只寫封面，不重寫報告，不送審<br>rtr.py：route 是聊天模型，看報告自己交出去。警示命中給 review，缺件不是無給 supplement，兩個都有先 review，其餘給 draft<br>不准自己講完結論。山海進草稿，當沒過<br>試跑 `uv run python bank_assistant/rtr.py`，對話編號 rtr<br>jev.py：route 不聊天。POST /v1/decisions，state 是報告，三個部門裡挑一個。回哪個名字就只啟動那顆。不包成 tool<br>DECISION_MODEL 預設 vcr-auto。指定 Jev 用 openrouter@typesafe/jev-1.13<br>這支用山海範例報告單跑。要接上一條，把 JevRoute 排在 revise 後面，讀同一份 report 和 faults<br>試跑 `uv run python bank_assistant/jev.py` | 講義<br>Google ADK<br>loop.py<br>rtr.py<br>jev.py |
| 第二天<br>第4堂 | 第1節 | 09:00 – 09:50 | MCP<br>(查詢不在這支程式裡) | 四支查詢改由外面的伺服器提供<br>停掉伺服器，300 萬不該再出現<br>這一層拿掉，退回第一天的查詢 | 講義<br>Google ADK<br>查詢伺服器 |
| 第二天<br>第4堂 | 第2節 | 10:00 – 11:00 | RAG<br>(規定在資料夾) | 辦法與公告放檢索，不放案件檔<br>新葉食品警示乾淨，仍因公告駁回<br>拿掉資料夾還寫得出條號，當沒過<br>占用狀態仍只走 API | 講義<br>Google ADK<br>辦法資料夾 |
| 第二天<br>第5堂 | 第3節 | 11:10 – 12:05 | SKILL<br>(做法不抄條文) | 做法包只寫步驟與欄位，不准抄條號<br>換辦法 B，上限改 500 萬，做法包不改<br>禾豐 800 萬的路徑要跟著變<br>沒變，就是門檻寫進人設或做法包<br>description 寫何時用，細節放 references。停用這包，欄位檢查要消失。scripts 不開 | 講義<br>Google ADK<br>做法包 |
| 第二天<br>第5堂 | 第4節 | 12:15 – 13:10 | Multi-Agent<br>(問完自己寫回) | 父層把覆核員當工具叫來<br>問完自己寫回經辦<br>第一天第 6 節的 RTR 仍是把報告交給部門 | 講義<br>Google ADK |
| 第二天<br>第6堂 | 第5節 | 14:10 – 15:05 | SandBox<br>(成數不准心算) | 800 萬對既有額度 300 萬的成數在沙盒裡算<br>模型不准心算<br>沒有沙盒呼叫卻寫出成數，當沒過 | 講義<br>Google ADK |
| 第二天<br>第6堂 | 第6節 | 15:15 – 16:10 | Deploy<br>(掛成服務再走一件) | 同一顆 agent 掛成服務<br>現場再走一件禾豐 | 講義<br>Google ADK |

注意事項：
1. 升級方式對齊 Agent Dungeon：同一件禾豐，每一節只加一層。拿掉這一層，行為要退回上一節。第 3、第 4 節是同一圈 ReAct，第 4 節不另加機制。
2. 第 1 堂第 1 節含環境安裝與兩套身份。第 1 堂第 2 節起為原第 2 堂上移。LOOP／RTR 佔第一天第 6 節。第二天六節依序是 MCP、RAG、SKILL、Multi-Agent、SandBox、Deploy。
3. Lv4 身份在第 1 節，Lv5 訊息串在第 2 節。ReAct 佔第 3、第 4 節，不再拆成 Lv6 工具和 Lv7 先查再講。MCP、檢索、做法包、多代理、沙盒、部署不是 Dungeon 關卡，不編號。
4. 第二天第 4 節把覆核員當工具。問完由父層寫回經辦。第一天第 6 節的 RTR 仍把報告交給部門。
5. 午餐 13:10–14:10，不計入 12 小時。日期未排，表內以第一天、第二天標示。
6. 全程合成資料。模型不寫核貸。狀態只有草稿、補件、升級、送審。一組約 4 人，至少 1 人會改 Python。
