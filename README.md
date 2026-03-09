# Assignment 1: Financial Assistant

> Build Your First Question Answering Agent (Raw Python & Function Calling)

## 簡介

這是一個使用 OpenAI Function Calling 功能實現的 CLI 財務助理聊天機器人，可以查詢匯率和股票價格。

## 功能特色

- 使用 OpenAI API (gpt-4o-mini) 實現 Function Calling
- 支援平行工具呼叫 (Parallel Tool Calls)
- 對話記憶功能 (Context Window)
- 結構化輸出 (Structured Outputs with strict: true)
- 優雅的錯誤處理
- Slash Commands 快速指令 (支援 Tab 自動補全)

## 環境需求

- Python 3.8+
- OpenRouter API Key (或 OpenAI API Key)

## 安裝步驟

### 1. 複製專案

```bash
git clone <your-repo-url>
cd "Assignment 1"
```

### 2. 建立虛擬環境 (建議)

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

### 3. 安裝相依套件

```bash
pip install -r requirements.txt
```

### 4. 設定環境變數

複製 `.env.example` 為 `.env` 並填入你的 API Key：

```bash
cp .env.example .env
```

編輯 `.env` 檔案：

```
OPENROUTER_API_KEY=your-actual-api-key-here
```

> 注意：請勿將 `.env` 檔案上傳至 Git

## 執行方式

```bash
python main.py
```

啟動後會看到以下畫面：

```
==================================================
  Financial Assistant
  Type '/' for commands, '/help' for help
==================================================

You:
```

## Slash Commands 快速指令

輸入 `/` 後按 Tab 可顯示可用指令選單：

| 指令 | 功能 | 範例 |
|------|------|------|
| `/exit` | 退出程式 | `/exit` |
| `/help` | 顯示幫助說明 | `/help` |
| `/price <symbol>` | 快速查股價 | `/price AAPL` |
| `/rate <pair>` | 快速查匯率 | `/rate USD_TWD` |
| `/clear` | 清除對話記憶 | `/clear` |

也可使用自然語言對話，或輸入 `exit`、`quit`、`bye` 退出程式。

## 驗證步驟 (Demo Video Tasks)

以下是作業要求的五個測試任務，可用於驗證程式功能：

### Task A: Persona (身分確認)

```
You: Who are you?
```

預期結果：Agent 回覆自己是 Financial Assistant

### Task B: Single Tool (單一工具呼叫)

```
You: What is the price of NVDA?
```

預期結果：
- Debug log 顯示呼叫 `get_stock_price({"symbol": "NVDA"})`
- 回傳價格 `190.00`

### Task C: Parallel Tools (平行工具呼叫)

```
You: Compare the stock prices of AAPL and TSLA.
```

預期結果：
- Debug log 顯示一次呼叫兩個 tool calls
- `get_stock_price({"symbol": "AAPL"})` -> `260.00`
- `get_stock_price({"symbol": "TSLA"})` -> `430.00`
- Agent 比較兩者價格

### Task D: Memory Test (記憶測試)

Step 1:
```
You: My name is Alice.
```

Step 2:
```
You: What is my name?
```

預期結果：Agent 正確回答 "Alice" (或你輸入的名字)

### Task E: Error Handling (錯誤處理)

```
You: What is the price of GOOG?
```

預期結果：
- Debug log 顯示 `{"error": "Data not found"}`
- Agent 優雅地告知找不到資料，程式不會崩潰

## 支援的查詢資料

### 匯率 (Exchange Rates)

| 貨幣對 | 匯率 |
|--------|------|
| USD_TWD | 32.0 |
| JPY_TWD | 0.2 |
| EUR_USD | 1.2 |

### 股票價格 (Stock Prices)

| 股票代碼 | 價格 |
|----------|------|
| AAPL | 260.00 |
| TSLA | 430.00 |
| NVDA | 190.00 |

## 專案結構

```
Assignment 1/
├── main.py           # 主程式
├── requirements.txt  # 相依套件
├── .env.example      # 環境變數範例
├── .env              # 環境變數 (不上傳)
├── .gitignore        # Git 忽略檔案
├── README.md         # 說明文件
├── PLAN.md           # 開發計畫
└── REQUIREMENTS.md   # 作業需求
```

## 技術實現

### Data Flow Architecture

```
                              ┌─────────────────┐
                              │   tools (JSON)  │
                              │  Tool Schemas   │
                              └────────┬────────┘
                                       │
                                       │ LLM reads tool definitions
                                       ▼
┌──────────────┐      ┌─────────────────────────────┐      ┌──────────────┐
│   messages   │◄──── │        Agent Loop           │────► │  LLM API     │
│ Chat History │      │       (Main Loop)           │      │  OpenRouter  │
└──────────────┘      └───────────────┬─────────────┘      └──────────────┘
                                      │
                                      │ Tool call requests
                                      ▼
                         ┌─────────────────────────┐
                         │    available_functions  │
                         │    (Function Registry)  │
                         └────────────┬────────────┘
                                      │
                                      │ Execute function
                                      ▼
                    ┌─────────────────────────────────────┐
                    │         Mock Data Functions         │
                    │  ┌───────────────────────────────┐  │
                    │  │     get_stock_price()         │  │
                    │  │     get_exchange_rate()       │  │
                    │  └───────────────────────────────┘  │
                    └─────────────────────────────────────┘
```

### Function Map (字典派發)

使用 Python Dictionary 進行工具路由，避免 if-else 鏈：

```python
available_functions = {
    "get_exchange_rate": get_exchange_rate,
    "get_stock_price": get_stock_price,
}
```

### Structured Outputs

所有工具定義都使用 `strict: true` 和 `additionalProperties: false`：

```python
{
    "type": "function",
    "function": {
        "name": "get_stock_price",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {...},
            "required": ["symbol"],
            "additionalProperties": False,
        },
    },
}
```

### Parallel Tool Calls

迴圈處理所有 tool calls，全部執行完畢後再呼叫 LLM：

```python
while response_message.tool_calls:
    for tool_call in response_message.tool_calls:
        # 執行每個 tool call
        ...
    # 所有 tool calls 完成後再呼叫 LLM
    response = client.chat.completions.create(...)
```

## 授權

本專案僅供學術用途。