# Assignment 2: Reasoning & Action Taking (ReAct Agent)

- Due Date: 2026/03/12 ~ 2026/03/25

## Objective

實作一個具備韌性的 ReAct Agent，能透過 Thought -> Action -> Observation 迴圈回答複雜問題。
除了基本的工具使用，需展現 Reflection（自我修正）與 Planning（任務拆解）能力。

## System Setup

| 項目       | 要求                                  |
|------------|---------------------------------------|
| LLM Engine | gpt-4o-mini                           |
| Search API | Tavily（推薦）/ Serper.dev / DuckDuckGo |
| API Keys   | 必須放在 `.env`，不得上傳至 GitHub     |

## ReAct Loop 核心機制

```
1. Thought  -- LLM 思考下一步
2. Action   -- 呼叫工具（Search / Calculate）
3. Observation -- 工具回傳結果
4. Reflection  -- 若結果不理想，反思並調整策略
5. 重複直到取得答案（上限 5 輪）
```

## Tasks（須用同一個 Agent 實例回答全部）

### Task 1: Planning & Quantitative Reasoning

- Question: "What fraction of Japan's population is Taiwan's population as of 2025?"
- 考驗：Task Decomposition（分別搜尋兩國人口再計算比例）

### Task 2: Technical Specificity

- Question: "Compare the main display specs of iPhone 15 and Samsung S24."
- 考驗：Data Retrieval（找到 60Hz vs 120Hz 等具體差異）

### Task 3: Resilience & Reflection Test

- Question: "Who is the CEO of the startup 'Morphic' AI search?"
- 考驗：搜尋失敗時能 Reflect 並調整搜尋策略

## Critical Requirements

1. **Few-Shot Prompting**: System Prompt 至少包含一個完整的 ReAct 範例（One-shot）
2. **Stop Sequences**: LLM 產生 Action 後必須停止，不可幻想 Observation
3. **Loop Limits**: 最多 5 步迭代
4. **Single Agent**: 不可針對不同 Task 建立不同 Agent 或切換 Prompt

## Deliverables

| 檔案               | 說明                       |
|--------------------|----------------------------|
| `agent.py`         | Agent 類別（ReAct 迴圈實作） |
| `tools.py`         | 搜尋工具 wrapper           |
| `main.py`          | 執行腳本                   |
| `.env.example`     | 環境變數模板               |
| `requirements.txt` | 依賴套件清單               |
| `report.pdf`       | 分析報告                   |

## Report Requirements (report.pdf)

### Section 1: Implementation Logic

- 貼出完整 System Prompt，標記 Few-Shot Example 並解釋為何有效
- 說明 Python 如何將 Observation 回饋至 LLM context window

### Section 2: Benchmark Traces

對每個 Task 貼出 Console Trace 並分析：
- Task 1: 是否有 Task Decomposition？
- Task 2: 是否搜尋到具體規格差異？
- Task 3: 搜尋失敗時是否有 Reflect 並重試？

## Grading Rubric

| 項目                                    | 分數 |
|-----------------------------------------|------|
| Agent Architecture（結構 + ）             | 20   |
| The Loop（ReAct 迴圈 + Stop Logic）       | 20   |
| Tool Integration（Search API + 錯誤處理） | 15   |
| Task 1 Report（Planning 拆解證據）        | 15   |
| Task 2 Report（搜尋到具體規格）           | 15   |
| Task 3 Report（Reflection 自我修正）      | 15   |

## Resources

- ReAct Paper: Yao, S., et al. (2023). ReAct: Synergizing Reasoning and Acting in Language Models.
- Tavily API: https://tavily.com
- ReAct - Prompt Engineering Guide: https://www.promptingguide.ai/techniques/react
