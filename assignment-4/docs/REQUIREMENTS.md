# Assignment 4: Requirements

> KG-based QA for NCU Regulations

## Assignment Overview

實作一個以 Neo4j Knowledge Graph 為核心的校規問答系統。從 NCU 英文版規章 PDF 中抽取結構化規則，建立固定的 KG Schema，並透過 Cypher 查詢檢索證據後生成 grounded answer。

核心評分重點：**Retrieval quality** 與 **Grounding quality**。系統必須能正確檢索到相關條文，並根據檢索結果回答，不能直接把整份規章餵給 LLM。

---

## Task A: PDF to SQLite ETL

### Requirements

- 使用 `pdfplumber` 解析 6 份 NCU 規章 PDF
- 將資料存入 SQLite：`ncu_regulations.db`
- 表格結構：
  - `regulations(reg_id, name, category)`
  - `articles(reg_id, article_number, content)`
- PDF 清單：
  - `ncu1.pdf` - NCU General Regulations
  - `ncu2.pdf` - Course Selection Regulations
  - `ncu3.pdf` - Credit Transfer Regulations
  - `ncu4.pdf` - Grading System Guidelines
  - `ncu5.pdf` - Student ID Card Replacement Rules
  - `ncu6.pdf` - NCU Student Examination Rules

### Implementation

- 檔案：`setup_data.py`
- 兩種解析模式：`article` 模式（Article N）與 `numbered` 模式（N.）
- 清理多餘空白與換行

---

## Task B: Knowledge Graph Construction

### Fixed Schema

```
(:Regulation)-[:HAS_ARTICLE]->(:Article)-[:CONTAINS_RULE]->(:Rule)
```

- **Article** 屬性：`number`, `content`, `reg_name`, `category`
- **Rule** 屬性：`rule_id`, `type`, `action`, `result`, `art_ref`, `reg_name`
- **Full-text Indexes**：`article_content_idx` (on Article.content), `rule_idx` (on Rule.action, Rule.result)

### Requirements

- 從 SQLite 讀取資料並建立 Neo4j 節點與關係
- 使用本地 LLM（`Qwen/Qwen2.5-3B-Instruct`）從每篇 Article 的 `content` 抽取結構化 Rules
- 每次建圖前清除舊資料：`MATCH (n) DETACH DELETE n`
- 需處理無效 Rule（`action` 或 `result` 為空則跳過）
- 需為 Rule 產生唯一 `rule_id` 並去除語意重複的 Rule
- 最後輸出 Coverage Audit：`covered_articles / total_articles`

### Implementation

- 檔案：`build_kg.py`
- `extract_entities(article_number, reg_name, content)`：LLM-based rule extraction，回傳 `{"rules": [...]}`
- `build_fallback_rules(article_number, content)`：可選的 deterministic fallback
- 使用 `session.run()` 分批寫入 Neo4j

---

## Task C: Query System (Retrieval + Generation)

### Public API Contract

必須保持以下函數簽名不變，供 `auto_test.py` 呼叫：

- `generate_text(messages, max_new_tokens=220)`
- `get_relevant_articles(question)`
- `generate_answer(question, rule_results)`

### Requirements

1. **Entity Extraction**
   - `extract_entities(question)`：解析問題為 `{"question_type": ..., "subject_terms": [...], "aspect": ...}`

2. **Cypher Query Builder**
   - `build_typed_cypher(entities)`：回傳 `(typed_query, broad_query)`
   - `typed_query`：針對 `Rule` 的 full-text search
   - `broad_query`：針對 `Article` 的 full-text search，再透過 `CONTAINS_RULE` 撈出關聯 Rule

3. **Article Retrieval**
   - `get_relevant_articles(question)`：執行 typed + broad 兩條查詢，合併、排序、去重後回傳 rule dict list

4. **Answer Generation**
   - `generate_answer(question, rule_results)`：只根據檢索到的 Rules 生成答案
   - 禁止直接把原始規章全文餵給模型
   - 若無足夠證據，回傳 `"Insufficient rule evidence to answer this question."`

### Implementation

- 檔案：`query_system.py`
- 使用本地 `llm_loader.py` 載入的 HuggingFace pipeline
- 清除環境變數中的 proxy 設定以避免連線干擾

---

## Task D: Automated Evaluation

### Requirements

- `auto_test.py` 必須能直接使用 `test_data.json` 執行評分
- 評分方式：LLM-as-a-Judge（`generate_text`）
- Judge prompt 要求輸出單一字：`PASS` 或 `FAIL`
- 共 20 題測試案例，涵蓋考試規則、學生證補發、畢業學分政策

### Test Data Distribution

| 來源 | 題號 | 主題 |
|------|------|------|
| ncu6.pdf | 1-7 | 考試規則（遲到、作弊、補考等） |
| ncu5.pdf | 8-10 | 學生證補發規定 |
| ncu1.pdf | 11-20 | 畢業與學術政策（學分、成績、退學等） |

### Implementation

- 檔案：`auto_test.py`
- Preflight check：確認 Neo4j 連線正常且 Rule nodes > 0
- 輸出每題的 Bot Answer、Judge Verdict、執行時間
- 最後輸出總正確率（Accuracy）

---

## Report Requirements (README.md)

README.md 即為報告，需包含以下內容：

1. **KG Schema Design**
   - 說明為何採用 `Regulation -> Article -> Rule` 三層結構
   - 說明 Node 與 Relationship 的屬性設計理由
   - 附上 Neo4j Browser 截圖（顯示關鍵 nodes 與 relationships）

2. **Cypher Query Design**
   - 解釋 `typed_query` 與 `broad_query` 的分工
   - 說明 full-text index 的使用方式
   - 提供實際使用的 Cypher 範例

3. **Failure Analysis & Improvements**
   - 列出 `auto_test.py` 中答錯的題目與原因分析
   - 說明針對錯誤做了哪些改進（prompt engineering、fallback rules、query rewriting 等）

---

## Technical Constraints

- **Python**: 3.11
- **Graph DB**: Neo4j（建議以 Docker 啟動）
- **LLM**: 本地 HuggingFace 模型，預設 `Qwen/Qwen2.5-3B-Instruct`
- **禁止**：使用需要 API key 的雲端模型服務（OpenAI、Google、OpenRouter 等）
- **禁止**：不經 KG 檢索直接把完整規章內容傾倒給 LLM
- **執行順序**：`setup_data.py` -> `build_kg.py` -> `query_system.py`（手動測試）-> `auto_test.py`

---

## Required Repository Files

提交至 GitHub 的 repository 必須至少包含：

```
assignment-4/
├── README.md           # 報告
├── auto_test.py        # 自動評分腳本
├── build_kg.py         # KG 建構
├── llm_loader.py       # 本地模型載入
├── query_system.py     # 問答系統
├── requirements.txt    # Python 相依套件
├── setup_data.py       # PDF 解析與 SQLite 初始化
├── .gitignore          # 忽略 env、cache、db 等
└── source/             # 6 份 NCU PDF 規章
```
