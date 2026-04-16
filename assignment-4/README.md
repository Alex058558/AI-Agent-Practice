# Assignment 4: KG-based QA for NCU Regulations

> Retrieval-Augmented Generation with Neo4j Knowledge Graph

## Project Structure

```
assignment-4/
├── README.md              # 報告（本文件）
├── setup_data.py          # PDF → SQLite ETL
├── build_kg.py            # Neo4j KG 建構
├── query_system.py        # 問答系統
├── auto_test.py           # 自動評分
├── llm_loader.py          # 本地 HF 模型載入
├── requirements.txt       # Python 相依套件
├── .gitignore             # Git 忽略規則
├── test_data.json         # 測試案例
├── source/                # NCU PDF 規章（待取得）
├── docs/                  # 長期規格文件
│   ├── README.md
│   └── REQUIREMENTS.md
└── .workflow/             # 短週期運作文件
    ├── HANDOVER.md
    └── PROGRESS.md
```

## Quick Links

- [詳細需求與規格](./docs/REQUIREMENTS.md)

