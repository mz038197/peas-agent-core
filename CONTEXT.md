# PEAS Agent

學生在 workspace 裡跟一個 ReAct agent 對話。這個 agent 能用的工具來自三個不同地方。

## Language

**內建工具**:
Agent 自己帶的工具，例如讀檔、執行指令。
_Avoid_: builtin、平台工具

**Workspace 工具**:
使用者放在自己 workspace 裡的工具。同名時留下順序是內建工具、Portal 工具、Workspace 工具，後面的被跳過。
_Avoid_: 自訂工具、外掛、學生工具

**Vans MCP Portal**:
遠端服務，提供 Notion、日曆、Gmail、Discord 這些能力。`peas-agent-mcp` 是連過去的客戶端，不是這個服務本身。
_Avoid_: MCP server、peas-agent-mcp、vans-mcp

**專案根**:
這次 agent 讀取學生專案檔案的資料夾。Portal 連線設定也放在這裡。每次建立 agent 都依當時的專案根讀取。
_Avoid_: 工作目錄、cwd、workspace

**Portal 工具**:
從 Vans MCP Portal 載入、給這個 agent 在對話裡呼叫的工具。跟內建工具、workspace 工具是三種來源。Portal 連不上時，對話仍可用另外兩種。Dream 整理記憶時不使用 Portal 工具。
_Avoid_: MCP 工具、遠端工具
