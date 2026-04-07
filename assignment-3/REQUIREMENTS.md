# Assignment 3: Requirements

> LangGraph RAG Agent Implementation

## Assignment Overview

實作一個 RAG (Retrieval-Augmented Generation) 系統，比較 LangGraph 狀態機架構與 LangChain ReAct Agent 的差異，並探索 Embedding Model 和 Chunk Size 對檢索品質的影響。

## Task A: LangChain ReAct Agent Prompt

### Requirements

- 使用 LangChain `AgentExecutor` 實作 ReAct Pattern
- Prompt 必須包含：
  - `Thought`: 推理下一步該做什麼
  - `Action`: 呼叫哪個 tool
  - `Action Input`: tool 的輸入
  - `Observation`: tool 執行結果
  - `Final Answer`: 最終答案
- 必須支援多輪 Thought-Action-Observation 迴圈（max_iterations=5）
- Final Answer 必須為英文（即使問題為中文）
- 必須處理 parsing errors

### Implementation

- 檔案：`langgraph_agent.py` → `run_legacy_agent()`
- Tool: `create_retriever_tool` 包裝 ChromaDB retriever
- Prompt template 包含 `{tools}`, `{tool_names}`, `{input}`, `{agent_scratchpad}`

---

## Task B: Intelligent Router

### Requirements

- 根據問題內容自動路由到對應的財報資料庫
- 分類類別：
  - `apple`: 問題僅涉及 Apple
  - `tesla`: 問題僅涉及 Tesla
  - `both`: 問題涉及兩家公司（比較型問題）
  - `none`: 問題與兩家公司無關
- 使用 LLM 進行分類判斷
- 輸出格式為 JSON: `{"datasource": "<category>"}`
- 需處理 JSON 解析失敗，fallback to "both"

### Implementation

- 檔案：`langgraph_agent.py` → `retrieve_node()`
- 使用 `json.loads()` 解析 LLM 輸出
- 根據分類結果決定檢索哪些 vector DB

---

## Task C: Relevance Grader

### Requirements

- 使用 LLM-as-a-Judge 判斷檢索結果是否相關
- Binary decision: `yes` / `no`
- Prompt 必須明確定義 relevance criteria:
  - 是否包含相關財務數據
  - 是否包含問題所需的關鍵字或事實
- 避免過度嚴格導致正確檢索被拒絕

### Implementation

- 檔案：`langgraph_agent.py` → `grade_documents_node()`
- 使用 `SystemMessage` + `HumanMessage` prompt
- Grade 用於決定是否需要 rewrite query

---

## Task D: Query Rewriter

### Requirements

- 當 Grader 判定檢索不相關時，重寫查詢以提升檢索效果
- 將模糊/非正式問題轉換為精確財務術語
- Example mappings:
  - "how much did they spend on new tech" → "Research and Development (R&D) expenses"
  - "how much money did they make" → "Total net sales / Total revenue"
  - "what they spent on buildings" → "Capital Expenditures (CapEx)"
- 輸出僅為重寫後的問題，無其他文字

### Implementation

- 檔案：`langgraph_agent.py` → `rewrite_node()`
- 使用 LLM 進行 rewriting
- 重寫後回到 retrieve node 重新檢索

---

## Task E: Final Generator

### Requirements

- 根據檢索到的 context 生成最終答案
- Prompt 必須包含：
  - Answer in English
  - Distinguish fiscal years (2024, 2023, 2022)
  - Cite source: `[Source: Apple 10-K]` or `[Source: Tesla 10-K]`
  - Honest "I don't know" when context insufficient
  - Include exact financial figures
- 禁止 hallucination

### Implementation

- 檔案：`langgraph_agent.py` → `generate_node()`
- 使用 `ChatPromptTemplate` 結構化 prompt
- Context 包含檢索到的 document chunks

---

## LangGraph State Machine Architecture

### Requirements

- 使用 `StateGraph` 建構狀態機
- Nodes:
  - `retrieve` → `grade_documents` → `generate` / `rewrite`
- Conditional Edges:
  - `grade_documents` → `generate` (if grade=yes)
  - `grade_documents` → `rewrite` (if grade=no and search_count <= 2)
- State TypedDict:
  - `question`: str
  - `documents`: str
  - `generation`: str
  - `search_count`: int
  - `needs_rewrite`: str

### Implementation

- 檔案：`langgraph_agent.py` → `build_graph()`
- 使用 `workflow.add_conditional_edges()` 實現分支邏輯

---

## Evaluation Requirements

### Test Cases (14 Questions)

| Category | Description | Count |
|----------|-------------|-------|
| Single Company | Apple 或 Tesla 單一財務數據 | 6 |
| Comparison | 兩家公司比較 | 2 |
| Unknown/Trap | 測試 hallucination 檔案 | 3 |
| Cross-language | 中文/英文混合問題 | 3 |

### Metrics

- Correctness: 14/14 test cases pass
- LLM-as-a-Judge grading
- Must contain expected facts
- Must NOT contain forbidden facts

---

## Experiment Requirements

### Variables to Compare

1. **Embedding Model**
   - MiniLM: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
   - BGE: `BAAI/bge-base-en-v1.5`

2. **Agent Architecture**
   - GRAPH: LangGraph state machine
   - LEGACY: LangChain ReAct Agent

3. **Chunk Size**
   - 1000: 適合小型文件
   - 2000: 保留表格完整性（大型財報）

### Expected Outcomes

| Config | GRAPH | LEGACY |
|--------|-------|--------|
| MiniLM + chunk1000 | ~78% | ~64% |
| MiniLM + chunk2000 | ~86% | ~57% |
| BGE + chunk2000 | 100% | ~50% |

---

## Report Requirements

- 分析三項實驗變數的影響
- 說明 LangGraph vs LangChain 的架構差異
- 討論 chunk size trade-off
- 包含實驗數據表格
- 結論與最佳配置建議

---

## Technical Constraints

- Python 3.10+
- ChromaDB for vector storage
- HuggingFace Embeddings (local)
- Multi-provider LLM: Google / OpenAI / Anthropic / OpenRouter
- Environment variables for configuration