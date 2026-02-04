---
description: 更新 Memory Bank 進度記錄
---

# Memory Bank 更新流程

在每次對話結束時，請執行以下步驟更新 memory-bank：

## 1. 更新 activeContext.md

更新 `memory-bank/activeContext.md` 檔案，包含：
- 最後更新時間
- 當前任務名稱
- 進行中的工作項目
- 待辦事項清單
- 相關腳本或檔案

## 2. 更新 progress.md

如果有完成的里程碑，更新 `memory-bank/progress.md`：
- 在對應日期下新增已完成項目
- 使用 ✅ 標記已完成
- 使用 ⏸️ 標記暫緩
- 使用 ❓ 標記待確認

## 3. 更新 CLAUDE.md

同步更新 `ARCHIVE/misc/CLAUDE.md` 的專案狀態區塊。

## 自動更新提示

當使用者說「更新 memory bank」或「更新進度」時，自動執行上述步驟。
