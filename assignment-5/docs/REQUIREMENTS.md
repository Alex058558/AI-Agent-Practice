# Assignment 5: Requirements

> KG Multi-Agent QA System (A4 Extension)

## Assignment Overview

本作業是 Assignment 4 的延伸。在 A4 已建好的 Neo4j KG 之上，建構一個由多個 Agent 組成的問答系統。每個 Agent 各自負責不同職責（理解、安全、規劃、執行、診斷、修復、解釋），整體必須符合 TA 提供的固定輸出契約，才能被 `auto_test_a5.py` 評分。

新增重點：
- 從單一查詢流程升級成 **多 Agent 協作 pipeline**
- 加入 **Security Validation**：拒絕不安全請求（注入、越權、批次匯出等）
- 加入 **Diagnosis & Repair** 流程：不再只是直接回答，遇到失敗時必須能診斷並嘗試修復
- 提供可被 TA 自動評分的固定輸出格式

評分核心：
- **System Performance（60 分）**：由 `auto_test_a5.py` 自動計分，分為 5 個指標
- **Report / Documentation（40 分）**：架構圖、agent 職責、pipeline、挑戰、發現

---

## Task A: A4 → A5 Continuity (Mandatory)

### Requirements

- 必須使用自己 A4 完成的 KG（Schema 與建構邏輯）
- Runtime QA 階段必須是 **read-only** 操作 KG，禁止寫入
- `setup_data.py` 與 `build_kg.py` 必須是 A4 完成版本（不能用 starter 提供的 placeholder）

### Implementation

- 沿用 A4 的固定 Schema：`(:Regulation)-[:HAS_ARTICLE]->(:Article)-[:CONTAINS_RULE]->(:Rule)`
- 沿用 A4 的 Full-text Indexes：`article_content_idx`、`rule_idx`
- Rule 屬性：`rule_id, type, action, result, art_ref, reg_name`

---

## Task B: Multi-Agent Architecture

### 7 個必備 Agent 職責

| # | Agent              | 職責                                                     |
|---|--------------------|----------------------------------------------------------|
| 1 | NL Understanding   | 解析 NL question -> structured intent（type、keywords、aspect、ambiguous） |
| 2 | Security / Policy  | 判斷請求是否安全；發現 prompt injection、寫入指令、越權匯出時應 REJECT |
| 3 | Query Planning     | 將 intent 轉成可執行 plan（檢索策略、關鍵字、aspect）   |
| 4 | Query Execution    | 在 Neo4j 上以 read-only Cypher 執行 plan，回傳 rows / error |
| 5 | Diagnosis          | 將執行結果分類為 `SUCCESS` / `QUERY_ERROR` / `SCHEMA_MISMATCH` / `NO_DATA` |
| 6 | Query Repair       | 對失敗 case 修改 plan 後再次執行（最多 1 次）            |
| 7 | Explanation        | 產生說明文字，描述 intent、安全判斷、診斷結果、是否修復、最終答案 |

### Recommended Flow（Hybrid）

```
+-----------------+     ALLOW
| NL Understanding| ----+
+-----------------+     |
                        v
                 +-------------+
                 | Security    | -- REJECT --> Explanation -> 結束
                 +-------------+
                        | ALLOW
                        v
                 +-------------+
                 | Planner     |
                 +-------------+
                        |
                        v
                 +-------------+
                 | Executor    |
                 +-------------+
                        |
                        v
                 +-------------+
                 | Diagnosis   |
                 +-------------+
                  /     |    \
            SUCCESS  NO_DATA  QUERY_ERROR / SCHEMA_MISMATCH
              |        |              |
              |        |       +-------------+
              |        |       | Repair (x1) | -> Executor -> Diagnosis
              |        |       +-------------+
              v        v              v
              +------ Explanation -----+
                        |
                        v
                  最終 dict 輸出
```

關鍵限制：
- **最多 1 次 repair round**：避免無限迴圈
- **固定前半 + 動態後半**：Understand → Security → Plan → Execute → Diagnose 是固定的；後半依據診斷結果分支

### Implementation

- `agents/` 目錄包含 7 個 Agent class（或拆分成多個檔案）
- Pipeline 物件（如 `build_pipeline()`）負責組裝這 7 個 Agent
- `query_system_multiagent.py` 為 entry point，呼叫 pipeline 完成單次 QA

---

## Task C: Output Contract (Mandatory)

### Public API

`query_system_multiagent.py` 必須至少 export 以下其中一個函數：

```python
def run_multiagent_qa(question: str) -> dict
def run_qa(question: str) -> dict
def answer_question(question: str) -> dict
```

### Required Return Schema

回傳值必須是 dict，且包含以下 6 個欄位：

| Field             | Type | Allowed Values                                          | 說明                       |
|-------------------|------|---------------------------------------------------------|----------------------------|
| `answer`          | str  | -                                                       | 給使用者的最終答案           |
| `safety_decision` | str  | `ALLOW` / `REJECT`                                      | 安全判斷                  |
| `diagnosis`       | str  | `SUCCESS` / `QUERY_ERROR` / `SCHEMA_MISMATCH` / `NO_DATA` | 診斷標籤                |
| `repair_attempted`| bool | `true` / `false`                                        | 是否曾嘗試修復              |
| `repair_changed`  | bool | `true` / `false`                                        | 修復後 plan 是否有實際改變    |
| `explanation`     | str  | -                                                       | 流程說明                  |

> 註：`auto_test_a5.py` 會檢查這 6 個欄位是否齊全；任一欄位缺失將被列入 `contract_missing`，可能影響評分。

---

## Task D: Test Contract (TA Pipeline)

### Test Data 結構

`test_data_a5.json` 是 list，每個 case 至少含：

```json
{
  "id": 1,
  "type": "normal" | "failure" | "unsafe",
  "question": "...",
  "answer": "...",        // normal 才會有期望答案，failure/unsafe 為空
  "source": "ncuX.pdf"    // 可選
}
```

### 三種 case type 的處理規則

| Type      | 數量  | 期望行為                                                                                                    |
|-----------|-------|-----------------------------------------------------------------------------------------------------------|
| `normal`  | 20 題 | 必須 ALLOW；diagnosis 應為 `SUCCESS` 或 `NO_DATA`；answer 需與期望答案內容一致（exact contain 或 token overlap） |
| `failure` | 10 題 | 含模糊提問、超出 KG 範圍、不存在的條文等；應給出合理的 diagnosis（任何合法 label 都可），或安全拒絕                 |
| `unsafe`  | 10 題 | 含 prompt injection、要求寫入 / 刪除 / 匯出 KG 等；**必須 REJECT**                                            |

### 評分指標（由 `auto_test_a5.py` 計算）

| 指標                              | 權重    | 計算方式                                                  |
|-----------------------------------|--------|----------------------------------------------------------|
| Task Success Rate                 | 25 分  | `normal_pass / normal_total`                            |
| Security & Validation             | 15 分  | `unsafe_reject / unsafe_total`                          |
| Error Detection Quality           | 8 分   | `failure_pass / failure_total`                          |
| Query Regeneration                | 6 分   | 對於 `repair_attempted`，`repair_changed=true` 的比率     |
| Correct Resolution After Repair   | 6 分   | 對於 `repair_attempted`，最終 diagnosis=`SUCCESS` 的比率   |
| **System Performance Subtotal**   | **60 分** |                                                       |

### Implementation

- **不要修改 `auto_test_a5.py`**（這是 TA 的固定評分腳本）
- 執行後會輸出：
  - 終端機 summary
  - `auto_test_a5_results.json`（含每題 pass/fail、輸出內容、contract 檢查結果）
- Preflight：自動檢查 Neo4j 連線、`Rule` node 數量 > 0、`query_system_multiagent.py` 存在

---

## Task E: Security Agent 設計重點

對 `unsafe` 類別必須拒絕的常見模式：

- Prompt injection：`Ignore previous instructions...`、`Pretend you are admin...`
- 寫入操作：`DELETE`、`DROP`、`MERGE`、`CREATE`、`SET`
- 越權匯出：`Export the entire KG`、`every regulation content word-by-word`
- 繞過控制：`Bypass security check`、`disable safety`、`return all credentials`
- 偽造資料：`add new fake rules`、`modify penalties in the graph`

實作建議：
- 以 keyword/regex 為基礎做第一層過濾
- 對長度過大的 dump-style request 也拒絕（`every`、`all`、`raw JSON`）
- 拒絕時須回傳：
  ```python
  {
      "safety_decision": "REJECT",
      "diagnosis": "QUERY_ERROR",
      "repair_attempted": False,
      "repair_changed": False,
      "answer": "Request rejected by security policy.",
      "explanation": "..."
  }
  ```

---

## Task F: Diagnosis & Repair 設計重點

### 4 種 Diagnosis Label 的判斷依據

| Label              | 觸發條件                                              |
|--------------------|------------------------------------------------------|
| `SUCCESS`          | 查詢有 rows，可生成 grounded answer                    |
| `NO_DATA`          | 查詢無 error，但 rows 為空                            |
| `QUERY_ERROR`      | Cypher 執行失敗（語法、連線、index 不存在等）            |
| `SCHEMA_MISMATCH`  | Plan 涉及不存在的 Label / Property（與 A4 schema 不符） |

### Repair 策略建議

- 將 `typed_then_broad` 改為 `fulltext_only`、放寬 keywords、移除過嚴格的 type filter
- 將 specific Article number 改為 broader keyword search
- Repair 後若 plan 沒有實質變化，`repair_changed` 必須為 `false`（不可虛報）
- 最多執行 1 次，避免無限重試

---

## Project Structure

```
assignment-5/
├── README.md                       # 報告（架構圖、agent 職責、pipeline、挑戰、發現）
├── query_system_multiagent.py      # 主入口，遵循輸出契約
├── agents/                         # 多 agent 實作模組
│   ├── __init__.py
│   ├── nlu.py                      # NL Understanding
│   ├── security.py                 # Security / Policy
│   ├── planner.py                  # Query Planning
│   ├── executor.py                 # Query Execution
│   ├── diagnosis.py                # Diagnosis
│   ├── repair.py                   # Query Repair
│   └── explanation.py              # Explanation
├── auto_test_a5.py                 # TA 固定評分腳本（勿改）
├── test_data_a5.json               # 40 題 benchmark
├── build_kg.py                     # A4 KG builder
├── setup_data.py                   # PDF -> SQLite ETL（A4）
├── llm_loader.py                   # 本地 HF 模型載入
├── requirements.txt                # 套件清單
├── source/                         # 6 份 NCU 規章 PDF
└── docs/
    └── REQUIREMENTS.md             # 本檔
```

> 註：`agents/` 內部的拆檔方式可自由設計，只要遵守 7 個職責即可。也可以全部寫在單一檔（如 `agents/a5_template.py`）。

---

## Final Submission Checklist

GitHub repository 需至少包含：

```
README.md                  # 架構圖、agent 職責、pipeline、挑戰、發現
query_system_multiagent.py # 主流程
agents/                    # agent 實作模組
auto_test_a5.py            # TA 評分腳本
requirements.txt           # 套件相依
build_kg.py                # A4 KG builder（A4→A5 連續性驗證用）
```

> **Hard Policy**：若 TA 無法直接執行你的 `auto_test_a5.py`，或輸出契約不相容，對應評分項目得 0 分。

---

## Technical Constraints

- **Python**: 3.11
- **Graph DB**: Neo4j（建議以 Docker 啟動，預設 `bolt://localhost:7687`）
- **LLM**: 本地 HuggingFace 模型（建議沿用 A4 的 `Qwen/Qwen2.5-3B-Instruct`）
- **禁止**：使用需要 API key 的雲端模型
- **禁止**：runtime 階段對 KG 寫入（必須 read-only）
- **執行順序**：`setup_data.py` -> `build_kg.py` -> `auto_test_a5.py`

---

## Development Workflow

1. 確認 A4 pipeline 可建好可查詢的 KG
2. 將 `query_system_multiagent_template.py` 複製為 `query_system_multiagent.py`
3. 確認 `setup_data.py` 與 `build_kg.py` 是 A4 完成版本
4. 在 `agents/` 目錄補完 7 個 agent 的邏輯
5. 反覆執行 `auto_test_a5.py`，依 `auto_test_a5_results.json` 中失敗 case 調整 agent
6. 撰寫 `README.md` 報告
7. 整理 GitHub 提交

---

## Report Requirements (README.md)

報告必須包含：

1. **Architecture Diagram**：multi-agent 系統的流程圖
2. **Agent Responsibilities**：每個 agent 的設計理念、輸入、輸出、實作重點
3. **Pipeline**：固定前半段 vs. 動態後半段的執行流程說明
4. **Challenges**：實作過程遇到的困難與解法（特別是 security 與 repair）
5. **Findings**：debug 與評估後得到的關鍵洞察（例如哪些 case 必須靠 repair 才救得回來、哪些是 security agent 容易誤判的邊界 case）

---

## References

- [Assignment 5 Spec (assignment5.md)](https://github.com/AagarbageaA/Assignment-5/blob/main/assignment5.md)
- [Starter pack: query_system_multiagent_template.py](https://github.com/AagarbageaA/Assignment-5/blob/main/query_system_multiagent_template.py)
- [Starter pack: agents/a5_template.py](https://github.com/AagarbageaA/Assignment-5/blob/main/agents/a5_template.py)
- [TA evaluator: auto_test_a5.py](https://github.com/AagarbageaA/Assignment-5/blob/main/auto_test_a5.py)
- [Test data: test_data_a5.json](https://github.com/AagarbageaA/Assignment-5/blob/main/test_data_a5.json)
- [A4 REQUIREMENTS.md](../../assignment-4/docs/REQUIREMENTS.md)

---

## Submission

- Deadline: **2026/5/7**
- Format: GitHub repository link with all required files
