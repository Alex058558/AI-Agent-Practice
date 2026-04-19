---
title: "Assignment 4: Knowledge Graph RAG Agent Report"
author: "CE8014 AI代理系統之設計與開發"
date: "2026-04-19"
geometry: margin=2.5cm
CJKmainfont: "Heiti TC"
mainfont: "Helvetica Neue"
monofont: "Menlo"
fontsize: 12pt
header-includes:
  - \usepackage{fancyhdr}
  - \usepackage{fancyvrb}
  - \usepackage{xcolor}
  - \pagestyle{fancy}
  - \fancyhead[L]{Assignment 4}
  - \fancyhead[R]{CE8014}
  - \fancyfoot[C]{\thepage}
  - \definecolor{pass}{RGB}{0,140,60}
  - \definecolor{fail}{RGB}{200,0,0}
  - \definecolor{bot}{RGB}{50,50,200}
  - \definecolor{step}{RGB}{140,140,140}
---

\newpage

# Section 1: Error Layer Diagnostics

本作業實作基於 Neo4j 的 Knowledge Graph (KG) RAG 系統，用以回答校園法規問題。系統使用 Qwen2.5-3B-Instruct 作為本地 LLM，經過三次迭代優化後，最終準確率達到 **80% (16/20)**。

RAG 系統的準確率受到三個處理階段的影響：

## 1.1 KG 抽取誤差 (Bucket A)

知識圖譜的建立 (`build_kg.py`) 依賴 LLM 從法規文本抽取結構化 Rule 節點。

**誤差來源**：

- LLM 需將法規文本轉換為 JSON 格式（type、action、result 等欄位）
- 結構複雜的法規（多重條件、數值限制、身分區別）可能抽取遺漏
- 源頭遺失資訊，後續檢索與生成無法挽回

## 1.2 檢索誤差 (Bucket B)

本系統使用 Neo4j 的全文檢索（基於 Lucene），採用 Lexical Search（字面匹配）。

**誤差來源**：

- 全文檢索只認字面上的字，不懂語意關聯
- 若問題用詞與 KG Rule 用詞不一致，正確答案排序較低
- 如 "penalty" vs "zero grade" 字面不相關

## 1.3 LLM 回答誤差 (Bucket C)

檢索結果經 Prompt 組裝後傳給 LLM 生成答案。

**誤差來源**：

- 若檢索結果包含多條不一致的 Rule（如多條 60 分與一條 70 分）
- LLM 可能受「雜訊干擾效應」影響，選擇出現頻率較高的錯誤答案

\newpage

# Section 2: Iteration History

## Stage 1: Baseline 建立

初次運行準確率：**70% (14/20)**

主要問題：

- 關鍵詞過濾過於嚴格（如 `ID` 因長度=2被濾除）
- 同義詞不匹配（如 "invigilator" vs "proctor"）
- 檢索排序不精確

## Stage 2: 檢索層優化

改進措施：

1. **關鍵詞白名單**：加入 `ID`、`PE` 等有意義的短詞
2. **同義詞映射**：將不同用詞映射到 KG 標準用詞
3. **Domain Keyword 注入**：根據問題類型補充相關關鍵詞
4. **檢索權重調整**：調整 typed_query 與 broad_query 的權重比例

**成果**：準確率提升至 **75% (15/20)**

## Stage 3: 生成層優化

改進措施：

1. **Article Snippet 輔助**：附上原始法規片段作為上下文
2. **Prompt 工程**：指示 LLM 如何處理數值衝突與身分區別
3. **Top-K 擴充**：LLM 可參考的 Rule 數量從 5 提升至 10

**成果**：準確率提升至 **80% (16/20)**

## Top-K 擴充實驗

| Top-K | 準確率      | FAIL題目          |
|-------|-------------|-------------------|
| 5     | 16/20 (80%) | Q5, Q17, Q18, Q19 |
| 10    | 16/20 (80%) | Q5, Q17, Q18, Q19 |

**結論**：擴大 Top-K 無法解決根本問題。若 KG 缺少 Rule 或檢索排序讓雜訊蓋過正確答案，增加 Context 只會增加雜訊干擾。

\newpage

# Section 3: Final Experiment Trace

```{=latex}
\begin{Verbatim}[fontsize=\small, frame=single, framesep=2mm, commandchars=\\\{\}]
[*] Starting LLM Evaluation for 20 Questions...

Q1: How many minutes late before barred from exam?
    \textcolor{bot}{Bot}: A student can be up to 20 minutes late...
    \textcolor{step}{Time}: 15.22s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q2: Can I leave the exam room 30 minutes after it starts?
    \textcolor{bot}{Bot}: No, you cannot leave the exam room...
    \textcolor{step}{Time}: 5.39s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q3: What is the penalty for forgetting my student ID?
    \textcolor{bot}{Bot}: The penalty is having five points deducted...
    \textcolor{step}{Time}: 3.40s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q4: What is the penalty for using electronic devices...
    \textcolor{bot}{Bot}: The penalty is a five-point deduction...
    \textcolor{step}{Time}: 3.68s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q5: What is the penalty for cheating, copying or passing notes?
    \textcolor{bot}{Bot}: The penalty is a five-point deduction...
    \textcolor{step}{Time}: 3.87s
    \textcolor{step}{Result}: \textcolor{fail}{FAIL} (expected: zero score + disciplinary)

Q6: Is a student allowed to take the question paper out?
    \textcolor{bot}{Bot}: According to Rule 9, violators receive zero grade...
    \textcolor{step}{Time}: 6.10s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q7: What happens if a student threatens the invigilator?
    \textcolor{bot}{Bot}: Zero grade + misconduct reported...
    \textcolor{step}{Time}: 5.55s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q8: What is the fee for replacing a lost EasyCard student ID?
    \textcolor{bot}{Bot}: The fee is NTD 200...
    \textcolor{step}{Time}: 4.12s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q9: What is the fee for replacing a lost Mifare student ID?
    \textcolor{bot}{Bot}: The fee is NTD 100...
    \textcolor{step}{Time}: 4.54s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q10: How many working days to get a new student ID?
    \textcolor{bot}{Bot}: 3 working days
    \textcolor{step}{Time}: 2.90s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q11: What is the minimum credits for undergraduate graduation?
    \textcolor{bot}{Bot}: 128 credits
    \textcolor{step}{Time}: 2.23s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q12: How many semesters of PE are required?
    \textcolor{bot}{Bot}: Five semesters
    \textcolor{step}{Time}: 2.14s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q13: Are Military Training credits counted?
    \textcolor{bot}{Bot}: Military Training is not counted...
    \textcolor{step}{Time}: 2.39s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q14: What is the standard duration for a bachelor's degree?
    \textcolor{bot}{Bot}: 4 years
    \textcolor{step}{Time}: 3.41s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q15: What is the maximum extension period?
    \textcolor{bot}{Bot}: Two academic years
    \textcolor{step}{Time}: 3.16s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q16: What is the passing score for undergraduate?
    \textcolor{bot}{Bot}: 60 marks
    \textcolor{step}{Time}: 3.02s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

Q17: What is the passing score for graduate students?
    \textcolor{bot}{Bot}: 60 marks
    \textcolor{step}{Time}: 3.72s
    \textcolor{step}{Result}: \textcolor{fail}{FAIL} (expected: 70 marks)

Q18: Under what condition will a student be dismissed?
    \textcolor{bot}{Bot}: Insufficient rule evidence
    \textcolor{step}{Time}: 2.66s
    \textcolor{step}{Result}: \textcolor{fail}{FAIL} (expected: failing > half credits)

Q19: Can a student take a make-up exam for failed grade?
    \textcolor{bot}{Bot}: Insufficient rule evidence
    \textcolor{step}{Time}: 2.98s
    \textcolor{step}{Result}: \textcolor{fail}{FAIL} (expected: No)

Q20: What is the maximum leave of absence duration?
    \textcolor{bot}{Bot}: Two academic years
    \textcolor{step}{Time}: 3.37s
    \textcolor{step}{Result}: \textcolor{pass}{PASS}

==============================
Summary: 16/20 PASS, 4/20 FAIL
Accuracy: 80.0%
==============================
\end{Verbatim}
```

\newpage

# Section 4: Failure Analysis

## Q5: 作弊處罰

| 項目       | 結果                                       |
|------------|--------------------------------------------|
| 問題       | What is the penalty for cheating?          |
| 正確答案   | Zero score + disciplinary action           |
| KG 狀態    | 有 Rule 8 "pass notes... zero grade"       |
| 檢索排序   | Rule 8 排第 8，Top 5 都是 5-point deduction |
| Root Cause | Bucket B - Lexical Search 不匹配           |

## Q17: 研究生及格分數

| 項目       | 結果                                             |
|------------|--------------------------------------------------|
| 問題       | What is the passing score for graduate students? |
| 正確答案   | 70 points                                        |
| KG 狀態    | 有 Article 59 "lowest passing grade is 70 marks" |
| 檢索排序   | 正確 Rule 在前，但多條 60 marks Rule 干擾         |
| Root Cause | Bucket C - 雜訊干擾效應                          |

## Q18: 退學條件

| 項目       | 結果                                              |
|------------|---------------------------------------------------|
| 問題       | Under what condition will a student be dismissed? |
| 正確答案   | Failing > half credits for 2 semesters            |
| KG 狀態    | 有 Article 21 包含完整退學條件                    |
| 檢索排序   | 排序不佳，關鍵詞被稀釋                             |
| Root Cause | Bucket B - 檢索排序問題                           |

## Q19: 補考規定

| 項目       | 結果                                             |
|------------|--------------------------------------------------|
| 問題       | Can a student take a make-up exam?               |
| 正確答案   | No                                               |
| KG 狀態    | 有 Article 20 "should not receive make-up exams" |
| 檢索排序   | PE Rule 排名較高，正確 Rule 排名較低              |
| Root Cause | Bucket B - 檢索排序問題                          |

## Root Cause 總結

| 題目 | Root Cause   | 層級     |
|------|--------------|----------|
| Q5   | 關鍵詞不匹配 | Bucket B |
| Q17  | 雜訊干擾效應 | Bucket C |
| Q18  | 檢索排序不佳 | Bucket B |
| Q19  | 檢索排序不佳 | Bucket B |

> Bucket A = KG 抽取誤差、Bucket B = 檢索誤差、Bucket C = LLM 回答誤差

**重要發現**：所有失敗題目的 KG 都包含正確答案，問題主要在檢索層與生成層。

\newpage

# Section 5: Reflection

## 5.1 Lexical Search 的限制

本系統使用 Lucene 全文檢索，存在先天限制：

- **字面匹配**：只認字面上的字，不懂語意關聯
- **同義詞問題**："penalty" 與 "zero grade" 字面不相關
- **排序稀釋**：重要關鍵詞若在多條 Rule 出現，權重被稀釋

## 5.2 改進方向

### 短期

- 同義詞表擴充
- 檢索權重調整
- Prompt 工程優化

### 長期（需要重建 KG）

- Rule 標籤優化（加入身分標籤）
- 引入 Semantic Search（Embedding 向量檢索）

## 5.3 Key Findings

1. **檢索層是 RAG 系統的天花板**：即使 KG 包含完整資訊，若 Lexical Search 無法精準匹配，LLM 也無法正確回答。

2. **Top-K 擴充不是萬靈丹**：擴大 Context Window 只會增加雜訊，無法解決檢索排序的根本問題。

3. **Lexical Search 的先天限制**：字面匹配不懂語意，需透過同義詞映射或向量檢索補足。

4. **三層誤差需分層診斷**：在改進系統前，需先確認是 Bucket A/B/C 哪一層的問題，避免改錯方向。