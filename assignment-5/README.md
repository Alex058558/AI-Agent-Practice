# Assignment 5: Multi-Agent KG QA System

> Multi-Agent Architecture for Knowledge Graph Question Answering

## Overview

本作業在 A4 KG RAG 系統基礎上，導入 Multi-Agent 架構與 Answer Normalization 優化，用以回答國立中央大學校園法規問題。

系統架構：

```
Question -> NLU -> Security -> Planner -> Executor -> Diagnosis -> Repair -> Explanation
                                              │
                                              ▼
                                         Neo4j KG
```

## Technical Stack

| 模組        | 技術                                  |
|-------------|---------------------------------------|
| KG Database | Neo4j 5.x                             |
| LLM         | Qwen2.5-3B-Instruct (local)           |
| Retrieval   | Lucene Fulltext (Lexical Search)      |
| Agents      | NLU / Security / Planner / Executor / Diagnosis / Repair / Explanation |
| Data Source | 6份 NCU 規章 PDF                      |

## Project Structure

```
assignment-5/
├── agents/
│   ├── a5_template.py              # Multi-Agent 實作
│   └── __init__.py
├── source/                          # NCU規章PDF (6份)
│   ├── ncu1.pdf                     # 學籍規定
│   ├── ncu2.pdf                     # 選課辦法
│   ├── ncu3.pdf                     # 學分抵免
│   ├── ncu4.pdf                     # 成績處理
│   ├── ncu5.pdf                     # 學生證補換發
│   └── ncu6.pdf                     # 考試規則
├── setup_data.py                    # PDF -> SQLite ETL
├── build_kg.py                      # KG 建構 (LLM 抽取 Rule)
├── query_system_multiagent.py       # 檢索 + 生成 + Postprocess
├── query_system_multiagent_template.py  # 原始模板
├── auto_test_a5.py                  # 40題自動評分 (20 normal + 10 unsafe + 10 failure)
├── llm_loader.py                    # HF 模型載入
├── test_data_a5.json                # 40題測試案例
├── report.md                        # 作業報告
├── report.pdf                       # PDF報告
├── trace/                           # 優化過程記錄與測試結果
├── docker-compose.yml               # Neo4j 容器設定
└── requirements.txt                 # Python 套件
```

## Quick Start

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 啟動 Neo4j

```bash
docker-compose up -d
```

### 3. 建立 KG

```bash
python build_kg.py
```

### 4. 執行測試

```bash
python auto_test_a5.py
```

### 5. 互動模式

```bash
python query_system_multiagent.py
```

## Final Results

| 指標           | 數值        |
|----------------|-------------|
| Normal QA      | 18/20 (90%) |
| Unsafe Query   | 10/10 (100%)|
| Failure Case   | 10/10 (100%)|
| Query Repair   | 8/8 (100%)  |
| **Overall**    | **38/40 (95%)** |

## Optimization Methods

| 方法                  | 效果                          |
|-----------------------|-------------------------------|
| Number Word Normalization | "Five points" -> "5 points" |
| Boolean Enrichment    | "No." -> "No. The student must wait 20 minutes." |
| Word Boundary Reranking | 區分 undergraduate vs graduate |
| Prompt Engineering    | 統一輸出格式 (digits, points) |

## Failure Analysis Summary

| 題目 | Root Cause                     | 層級            |
|------|--------------------------------|-----------------|
| Q9   | LLM 未理解 compound rule 結構  | Bucket C (生成) |
| Q18  | KG parsing 將條件拆成兩個 Rule | Bucket A (抽取) |

> 詳見 report.pdf

## Key Findings

1. **Multi-Agent 架構有效**：Security + Diagnosis + Repair 讓 unsafe/failure cases 全部通過
2. **Postprocess 優化顯著**：通用後處理方法將 normal QA 從 5/20 提升至 18/20
3. **KG Rule parsing 影響深遠**：Article 21 條件拆分導致 LLM 無法組合閱讀

## References

- [詳細需求與規格](./docs/REQUIREMENTS.md)
