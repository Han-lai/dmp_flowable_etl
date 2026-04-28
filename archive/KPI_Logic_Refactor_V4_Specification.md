# DMP Flowable KPI 指標定義規則書 (V4.1 當日即時消化模式)

## 1. 指標核心理念
本版本為 **「當日開單追蹤模式 (Same-day Cohort)」**。
*   **目標**：衡量當天產生的任務，在當天被消化的效率。
*   **核心限制**：所有指標判定必須以 **「任務開單日 (task_start_date)」** 為基準。
*   **排除對象**：任何「跨日結案」或「跨日認領」的舊任務動作，將不會出現在此報表中。

---

## 2. 三大指標判定邏輯 (以開單當日為唯一基準)

### 2.1 Done (當日即時結案)
*   **定義**：今天新產生、今天被認領、且今天就結案的任務。
*   **技術條件**：
    *   `task_start_date == snapshot_date`
    *   `task_claim_date == snapshot_date`
    *   `task_end_date == snapshot_date`

### 2.2 Doing (當日即時認領)
*   **定義**：今天新產生、今天被認領，但至午夜尚未結案的任務。
*   **技術條件**：
    *   `task_start_date == snapshot_date`
    *   `task_claim_date == snapshot_date`
    *   `task_end_date != snapshot_date`

### 2.3 Todo (當日純待辦)
*   **定義**：今天新產生，但至午夜尚未被領取、尚未結案的任務。
*   **技術條件**：
    *   `task_start_date == snapshot_date`
    *   `task_claim_date != snapshot_date`
    *   `task_end_date != snapshot_date`

---

## 3. 進度指標 (ACC)
*   **概念**：**Todo + Doing**。
*   **定義**：過去 7 天內新產生，且截至快照日尚未結案的任務。
*   **計算方式**：這 7 天內滿足 V4 條件的 Todo 與 Doing 聯集。

---

## 4. 預期數據變化 (重要警告)
*   **Done 數值將大幅下降**：因為它不再統計「以前開單、今天才做完」的任務。
*   **準確性**：這是衡量生產線「當天開單當天完成」能力的極致指標。

---
*文件更新日期: 2026-04-27*
*狀態: V4.1 實施中*
