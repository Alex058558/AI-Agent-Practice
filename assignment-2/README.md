# Assignment 2: ReAct Agent

> Reasoning & Action Taking with Reflection and Planning

## 簡介

這是一個實作 ReAct（Reasoning + Acting）迴圈的 CLI Agent，透過 Thought -> Action -> Observation 循環回答複雜問題，並具備 Reflection（自我修正）與 Planning（任務拆解）能力。

## 功能特色

- ReAct 迴圈（Thought / Action / Observation）
- Few-Shot Prompting（One-shot example in system prompt）
- Stop Sequence 防止 LLM 幻想 Observation
- Reflection：搜尋結果不佳時自動調整策略
- Planning：複雜問題自動拆解為子任務
- 最多 5 輪迭代限制
- Slash Commands 快速指令（支援 Tab 自動補全）

## 環境需求

- Python 3.8+
- OpenRouter API Key
- Tavily API Key

## 安裝步驟

### 1. 建立虛擬環境（建議）

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

### 2. 安裝相依套件

```bash
pip install -r requirements.txt
```

### 3. 設定環境變數

複製 `.env.example` 為 `.env` 並填入你的 API Keys：

```bash
cp .env.example .env
```

編輯 `.env` 檔案：

```
OPENROUTER_API_KEY=your-openrouter-api-key-here
TAVILY_API_KEY=your-tavily-api-key-here
MODEL=openai/gpt-4o-mini
```

> 注意：請勿將 `.env` 檔案上傳至 Git

## 執行方式

```bash
python main.py
```

啟動後會看到以下畫面：

```
==================================================
  ReAct Agent - Assignment 2
  Type '/' for commands, '/help' for help
==================================================

You:
```

## Slash Commands 快速指令

輸入 `/` 後按 Tab 可顯示可用指令選單：

| 指令       | 功能               | 範例       |
|------------|--------------------|------------|
| `/exit`    | 退出程式           | `/exit`    |
| `/help`    | 顯示幫助說明       | `/help`    |
| `/clear`   | 重置 Agent         | `/clear`   |
| `/tasks`   | 顯示所有預設任務   | `/tasks`   |
| `/run <n>` | 執行預設任務       | `/run 1`   |

也可使用自然語言輸入任意問題，或輸入 `exit`、`quit`、`bye` 退出程式。

## 預設任務（Demo Tasks）

### Task 1: Planning & Quantitative Reasoning

```
/run 1
```

問題：`What fraction of Japan's population is Taiwan's population as of 2025?`

預期行為：Agent 拆解任務，分別搜尋兩國人口後使用 `calculate` 工具計算比例。

### Task 2: Technical Specificity

```
/run 2
```

問題：`Compare the main display specs of iPhone 15 and Samsung S24.`

預期行為：搜尋並取得具體規格差異（例如 60Hz vs 120Hz）。

### Task 3: Resilience & Reflection Test

```
/run 3
```

問題：`Who is the CEO of the startup 'Morphic' AI search?`

預期行為：搜尋失敗時能 Reflect 並調整搜尋策略重試。

## 工具（Tools）

| 工具          | 說明                           |
|---------------|--------------------------------|
| `search`      | 使用 Tavily API 進行網路搜尋   |
| `calculate`   | 安全數學運算（使用 ast 模組）  |

## ReAct 迴圈架構

```
User Question
      │
      ▼
┌─────────────────────────────────────────┐
│               ReAct Loop               │
│                                         │
│  Thought  ──► Action ──► PAUSE          │
│                │                        │
│                ▼                        │
│          Dispatch Tool                  │
│                │                        │
│                ▼                        │
│         Observation                     │
│                │                        │
│                ▼                        │
│  (Reflect if poor result, retry)        │
│                │                        │
│         (max 5 iterations)              │
└─────────────────┬───────────────────────┘
                  │
                  ▼
               Answer
```

## 專案結構

```
assignment-2/
├── agent.py          # ReActAgent 類別（ReAct 迴圈實作）
├── tools.py          # search / calculate 工具 wrapper
├── main.py           # CLI 入口點（prompt_toolkit）
├── .env.example      # 環境變數範例
├── requirements.txt  # 相依套件清單
└── report.pdf        # 分析報告
```

## 授權

本專案僅供學術用途。
