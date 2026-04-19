# Assignment 4: KG-based QA for NCU Regulations

> Retrieval-Augmented Generation with Neo4j Knowledge Graph

## Overview

本作業實作基於 Neo4j Knowledge Graph 的 RAG 系統，用以回答國立中央大學校園法規問題。

系統架構：

```
PDF規章 → SQLite → Neo4j KG → Lexical Search → LLM → 回答
```

## Technical Stack

| 模組        | 技術                             |
|-------------|----------------------------------|
| KG Database | Neo4j 5.x                        |
| LLM         | Qwen2.5-3B-Instruct (local)      |
| Retrieval   | Lucene Fulltext (Lexical Search) |
| Data Source | 6份 NCU 規章 PDF                 |

## Project Structure

```
assignment-4/
├── source/                # NCU規章PDF (6份)
│   ├── ncu1.pdf           # 學籍規定
│   ├── ncu2.pdf           # 選課辦法
│   ├── ncu3.pdf           # 學分抵免
│   ├── ncu4.pdf           # 成績處理
│   ├── ncu5.pdf           # 學生證補換發
│   └── ncu6.pdf           # 考試規則
├── setup_data.py          # PDF → SQLite ETL
├── build_kg.py            # KG 建構 (LLM 抽取 Rule)
├── query_system.py        # 檢索 + 生成回答
├── auto_test.py           # 20題自動評分
├── llm_loader.py          # HF 模型載入
├── test_data.json         # 20題測試案例
├── ncu_regulations.db     # SQLite 中介資料庫
├── report.md              # 作業報告
├── report.pdf             # PDF報告
├── docker-compose.yml     # Neo4j 容器設定
└── requirements.txt       # Python 套件
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
python auto_test.py
```

### 5. 互動模式

```bash
python query_system.py
```

## Final Results

| 指標       | 數值             |
|------------|------------------|
| 測試準確率 | 80% (16/20)      |
| PASS題目   | Q1-4, Q6-16, Q20 |
| FAIL題目   | Q5, Q17-Q19      |

## Failure Analysis Summary

| Root Cause   | 層級            | 數量 |
|--------------|-----------------|------|
| 關鍵詞不匹配 | Bucket B (檢索) | 1    |
| 雜訊干擾效應 | Bucket C (生成) | 1    |
| 檢索排序不佳 | Bucket B (檢索) | 2    |

> 詳見 report.pdf

## Key Findings

1. **檢索層是 RAG 的天花板**：KG 有答案但 Lexical Search 無法匹配，LLM 也無法正確回答
2. **Top-K擴充非萬靈丹**：增加Context只增加雜訊，無法解決檢索排序根本問題
3. **Lexical Search先天限制**：字面匹配不懂語意，需同義詞映射或向量檢索補足

## References

- [詳細需求與規格](./docs/REQUIREMENTS.md)