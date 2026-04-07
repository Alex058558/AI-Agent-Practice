# Assignment 3: LangGraph RAG Agent

> Retrieval-Augmented Generation with LangGraph vs LangChain

## 簡介

這是一個實作 RAG（Retrieval-Augmented Generation）系統的專案，比較兩種 Agent 架構：

- **GRAPH (LangGraph)**：基於狀態機的 Agent，包含 Router、Grader、Generator、Rewriter 四個節點
- **LEGACY (LangChain ReAct)**：傳統的 ReAct Agent，使用 AgentExecutor 實現 Thought-Action-Observation 迴圈

## 功能特色

- 智能路由：根據問題內容自動路由到 Apple 或 Tesla 財報
- 文檔評分：過濾不相關的檢索結果
- 查詢重寫：檢索失敗時自動優化搜索查詢
- 多 LLM Provider 支援：Google Gemini、OpenAI、Anthropic、OpenRouter
- 可配置的 Embedding Model 與 Chunk Size
- 14 題測試用例評估

## 環境需求

- Python 3.10+
- OpenRouter API Key / OpenAI API Key / Google API Key

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

複製 `.env_example` 為 `.env` 並填入你的 API Keys：

```bash
cp .env_example .env
```

編輯 `.env` 檔案：

```bash
# 使用 OpenRouter
LLM_PROVIDER=openai
OPENAI_API_KEY=your-openrouter-api-key-here
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=google/gemma-4-31b-it

# 或使用 Google Gemini
LLM_PROVIDER=google
GOOGLE_API_KEY=your-google-api-key-here
GOOGLE_MODEL=gemini-2.0-flash

# RAG Config
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
CHUNK_SIZE=2000
CHUNK_OVERLAP=400
```

> 注意：請勿將 `.env` 檔案上傳至 Git

## 執行方式

### 1. 建立向量資料庫

```bash
python build_rag.py
```

### 2. 執行評估

```bash
# GRAPH 模式
python evaluator.py GRAPH

# LEGACY 模式
python evaluator.py LEGACY
```

## 實驗結果

| Config | GRAPH | LEGACY |
|--------|-------|--------|
| MiniLM + chunk1000 | 11/14 | 9/14 |
| MiniLM + chunk2000 | 12/14 | 8/14 |
| **BGE + chunk2000** | **14/14** | 7/14 |

**最佳配置**：Gemma 4-31b-it + BGE embedding + chunk_size=2000 + GRAPH

## 架構設計

### GRAPH Agent (LangGraph)

```
START
   │
   ▼
retrieve ──► grade_documents ──► decision?
   ▲              │                  │
   │              │                  ├── yes ──► generate ──► END
   │              │                  │
   │              │                  └── no ──► rewrite ──┘
   │              │                           (if search_count <= 2)
   └──────────────┘
```

### LEGACY Agent (LangChain ReAct)

```
User Question
      │
      ▼
┌─────────────────────────────────────────┐
│               ReAct Loop               │
│                                         │
│  Thought  ──► Action ──► Observation   │
│                │                        │
│                ▼                        │
│         (max 5 iterations)              │
└─────────────────┬───────────────────────┘
                  │
                  ▼
               Answer
```

## 專案結構

```
assignment-3/
├── config.py          # LLM provider 配置
├── build_rag.py       # 向量資料庫建立腳本
├── langgraph_agent.py # GRAPH 與 LEGACY Agent 實作
├── evaluator.py       # 14 題測試用例評估
├── data/              # PDF 財報文件
│   ├── FY24_Q4_Consolidated_Financial_Statements.pdf  # Apple 10-K
│   └── tsla-20241231-gen.pdf                          # Tesla 10-K
├── chroma_db/         # ChromaDB 向量資料庫
├── traces/            # 實驗評估記錄
├── .env_example       # 環境變數範例
├── requirements.txt   # 相依套件清單
└── report.pdf         # 分析報告
```

## 關鍵發現

1. **GRAPH 優於 LEGACY**：LangGraph 的狀態機架構更穩定，平均領先 4-7 分
2. **Embedding 選擇關鍵**：英文財報應使用英文專用的 BGE embedding
3. **Chunk Size 影響檢索**：大文件需要更大的 chunk_size (2000) 來保留表格完整性

## 授權

本專案僅供學術用途。

## 相關文件

- [REQUIREMENTS.md](./REQUIREMENTS.md) - 作業需求詳細說明