# 金融業 Google ADK 工作坊：12 小時

格式對齊升級版大綱。同一天的節數往下累加。

| 日期 | 節數 | 時間 | 教學主題 | 教學內容 | 教學工具 |
|---|---|---|---|---|---|
| 第一天<br>第1堂 | 第1節 | 09:00 – 09:50 | 建立 Agent 並寫入兩套身份<br>(同一份 agent.py) | 安裝 google-adk<br>.env 放 `VCR_API_KEY`、`MODEL_NAME=vcr-auto`、`BASE_URL=https://ai.vanscoding.com/v1`<br>`root_agent` 的 model 用 `OpenAILlm`，三個值從這三個環境變數讀<br>`_load_env()` 放在建立 `root_agent` 之前。直接跑 `agent.py` 時 ADK 不會先載 `.env`<br>建立 root_agent，temperature=0，指令先寫嚴格初審<br>三種執行都要跑過：`uv run adk web bank_assistant --port 8010`<br>`uv run adk run bank_assistant`<br>`uv run python bank_assistant/agent.py`<br>問「800 萬能不能做」，要說還要查<br>同一畫面再問，要答出禾豐食品<br>同一份檔把指令改成衝業績，新對話同一句，答案要分開<br>不准講既有額度 300 萬。講得出就是編的 | 講義<br>Google ADK（adk web / adk run / agent.py） |
| 第一天<br>第1堂 | 第2節 | 10:00 – 11:00 | Lv5 Memory<br>(訊息串不是案件檔) | 同一輪問「我剛問了哪一家」，要答得出<br>新開一輪再問，要答不出<br>執行 `uv run python bank_assistant/agent.py`。`run_debug` 把這句送出<br>預設寫入 `.adk/session.db`，編號 s1。關掉再執行，同一則還在<br>換 `session_id` 才是新的一輪。舊編號仍留在資料庫<br>`SESSION_STORE=memory` 關掉就沒了。`postgres` 用 `postgresql+asyncpg://`，先 `uv add asyncpg`<br>正式環境不靠 `input()` 和 `run_debug`。留下 `root_agent`，對話寫進資料庫<br>這一節不掛工具 | 講義<br>Google ADK |
| 第一天<br>第2堂 | 第3節 | 11:10 – 12:05 | Lv6 Tools<br>(會講變成查得到) | 四支查詢寫在 queries.py：get_customer、get_exposure、check_watchlist、get_registry<br>agent.py 的 tools 直接掛這四個普通函式。不用 LangChain 的 @tool<br>300 萬只寫在 queries.py。instruction 出現 300，當沒過<br>指令改成：沒呼叫不准講額度、警示、變更。新的一輪要再查一次<br>問禾豐額度，畫面上要有 get_exposure，答案是 300 萬<br>沒有工具呼叫卻講出 300 萬，當沒過<br>公司名稱對不上，或同時對上兩家，不猜、不帶出額度<br>山海的警示先寫進表。這一節只驗禾豐<br>退回上一節要把 tools 拿掉，指令改回「不准講額度」<br>這一節不掛 peas-agent-tools。那包是讀檔、改檔、跑命令，要另包才進得了 ADK | 講義<br>Google ADK<br>queries.py |
| 第一天<br>第2堂 | 第4節 | 12:15 – 13:10 | Lv7 Decision<br>(查完才准講) | 先呼叫工具，看結果，再回答<br>山海貿易要看到警示命中<br>把禾豐的結論複誦到山海身上，當沒過<br>沒查完就寫結論，當沒過 | 講義<br>Google ADK<br>合成進件檔 |
| 第一天<br>第3堂 | 第5節 | 14:10 – 15:05 | Planning<br>(一步做不完) | Sequential：先查再寫意見<br>Parallel：主檔、額度、變更登記一起查<br>Loop：意見缺欄就重寫，最多兩輪<br>這一節不分流、不送審<br>每步結果寫進 Output Key，下一步要讀得到 | 講義<br>Google ADK<br>案件檔 |
| 第一天<br>第3堂 | 第6節 | 15:15 – 16:10 | Route<br>(規則不交給模型) | Python 讀查詢結果再選路<br>北岸倉儲缺財簽，走補件<br>山海貿易名單命中，走升級<br>禾豐齊件只存草稿。模型自己改判，當沒過<br>結果要有路徑、依據、狀態三欄，不准只回一段話 | 講義<br>Google ADK<br>案件檔 |
| 第二天<br>第4堂 | 第1節 | 09:00 – 09:50 | RAG<br>(規定在資料夾) | 辦法與公告放檢索，不放案件檔<br>新葉食品警示乾淨，仍因公告駁回<br>拿掉資料夾還寫得出條號，當沒過<br>占用狀態仍只走 API | 講義<br>Google ADK<br>辦法資料夾 |
| 第二天<br>第4堂 | 第2節 | 10:00 – 11:00 | Procedure<br>(做法不抄條文) | 做法包只寫步驟與欄位，不准抄條號<br>換辦法 B，上限改 500 萬，做法包不改<br>禾豐 800 萬的路徑要跟著變<br>沒變，就是門檻寫進人設或做法包<br>description 寫何時用，細節放 references。停用這包，欄位檢查要消失。scripts 不開 | 講義<br>Google ADK<br>做法包 |
| 第二天<br>第5堂 | 第3節 | 11:10 – 12:05 | Confirm<br>(人按了才算數) | 送審必須人按確認，檔才變成送審<br>沒按就呼叫，要被擋下<br>補件、升級、駁回沒有送審鍵<br>對話說已送審、檔沒變，當沒過 | 講義<br>Google ADK<br>案件檔 |
| 第二天<br>第5堂 | 第4節 | 12:15 – 13:10 | Lv8 對齊<br>(錯了不准圓過去) | 工具失敗、缺參數、檔讀不到，要停下來講<br>不准改口說已經送審<br>四題卷：齊件、缺件、名單、公告<br>不安裝套件，不寫另一套工具迴圈 | 講義<br>Google ADK<br>四題卷 |
| 第二天<br>第6堂 | 第5節 | 14:10 – 15:05 | Demo<br>(拿掉這一層就退回) | 現場走一件，依據指給大家看<br>拿掉模型，狀態檔與確認紀錄還在<br>只展示接了模型，當沒 Demo<br>每組 8 分鐘 | 講義<br>Google ADK |
| 第二天<br>第6堂 | 第6節 | 15:15 – 16:10 | 本格空出 | 第 1 堂兩節合併後，後面各節上移一格。Demo 在上一節。 | — |

注意事項：
1. 升級方式對齊 Agent Dungeon：同一件禾豐，每一節只加一層。拿掉這一層，行為要退回上一節。
2. 第 1 堂第 1 節含環境安裝與兩套身份。第 1 堂第 2 節起為原第 2 堂上移。最後一格空出。
3. Lv4 身份、Lv5 訊息串、Lv6 工具、Lv7 先查再講，各占一節。Planning、分流、檢索、做法包、確認不是 Dungeon 關卡，不編號。
4. 第 6 堂第 1 節只借用 Lv8 的失敗處理：工具出錯要停，不准圓成已送審。不安裝 peas-agent-tool，不另寫一套工具迴圈。
5. 午餐 13:10–14:10，不計入 12 小時。日期未排，表內以第一天、第二天標示。
6. 全程合成資料。模型不寫核貸。狀態只有草稿、補件、升級、送審。一組約 4 人，至少 1 人會改 Python。
