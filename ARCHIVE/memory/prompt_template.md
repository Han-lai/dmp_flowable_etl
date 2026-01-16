# 階段型 Prompt 模板

複製以下模板，填入內容後使用：

---

```markdown
## Phase
[ ] Exploration
[ ] MVP
[ ] Hardening

## Goal
[單一明確目標，一句話]

## Tasks
1. [具體可執行的任務]
2. [具體可執行的任務]

## Constraints
- ❌ [禁止事項]
- ❌ [禁止事項]

## Output Expectation
- 格式：[SQL / Python / Markdown / 其他]
- 檔案位置：[路徑]
- 其他要求：[如有]
```

---

## 範例

```markdown
## Phase
[x] MVP

## Goal
建立 FlowableTaskStats 的增量同步 SQL

## Tasks
1. 查詢 LastUpdatedTime 作為增量條件
2. 寫入 bronze.common_flowable_task_stats
3. 記錄同步狀態到 _sync_log

## Constraints
- ❌ 不要優化效能
- ❌ 不要加入錯誤處理
- ❌ 不要建立新表

## Output Expectation
- 格式：SQL
- 檔案位置：sync/incremental_flowable_task_stats.sql
```
