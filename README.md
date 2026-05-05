# Agentic AI

AI Agent 開發實戰課程作業集。每個 assignment 為獨立的實作練習，涵蓋從基礎 Function Calling 到進階 Agent 架構的完整學習路徑。

## Assignments

| # | 主題                | 說明                                                                                              | 連結                            |
|---|---------------------|---------------------------------------------------------------------------------------------------|---------------------------------|
| 1 | Financial Assistant | 使用 Raw Python + Function Calling 打造 CLI 財務助理                                              | [assignment-1](./assignment-1/) |
| 2 | ReAct Agent         | 從零實作 ReAct (Reasoning + Acting) Agent，具備 Reflection 與 Planning 能力                        | [assignment-2](./assignment-2/) |
| 3 | LangGraph RAG       | 實作 RAG 系統比較 LangGraph 與 LangChain 架構，探索 Embedding Model 與 Chunk Size 對檢索品質的影響 | [assignment-3](./assignment-3/) |
| 4 | KG-based QA         | Neo4j Knowledge Graph RAG 系統，使用 Lucene 全文檢索回答 NCU 校規問題，準確率 80%                   | [assignment-4](./assignment-4/) |
| 5 | Multi-Agent KG QA   | 在 KG RAG 基礎上導入 7-Agent 架構（Security/Diagnosis/Repair），加入 Answer Normalization 與 Boolean Enrichment 優化 | [assignment-5](./assignment-5/) |

## 技術棧

- Python
- OpenAI API (gpt-4o-mini) / OpenRouter / Google Gemini
- Function Calling / Tool Use
- Tavily Search API
- ReAct Pattern (Thought -> Action -> Observation)
- LangGraph / LangChain
- ChromaDB / HuggingFace Embeddings
- Neo4j Knowledge Graph
- Lucene Fulltext Search
- Multi-Agent Pipeline (NLU / Security / Planner / Executor / Diagnosis / Repair / Explanation)
- Qwen2.5-3B-Instruct (Local LLM)
