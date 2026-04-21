# 當前工作脈絡 (Active Context)

**最後更新**: 2026-04-21

---

## 🎯 當前焦點 (Current Focus)

### ⏩ 進行中
- **週/月報表數據偏移修正**: 診斷出週 (Week) 與月 (Month) 數據不正確是因 `UNION ALL` 分支使用了 `BETWEEN` 導致整段區間快照被聯集。計畫改為「期末單日快照 (Period-End Snapshot)」邏輯。
- **W1 (跨年週) 數據偏差診斷**: 目前正在排查 W1 (12/29-31) 在 NBU/E5 產線上顯示 12 筆（預期）與 82 筆（資料庫現狀）的最後一公里落差。

### ✅ 近期已解決
- **L5 數據一致性優化 (Bitmap 架構遷移 - V3.2)**: 
    - 成功由 Silver DISTINCT 方案轉型為 **Gold Layer Bitmap (V3)** 方案。
    - 實作了 **Identity-Preserving Exclusion (身份唯一排除法)**：確保 `Todo + Doing + Done = Total`。
    - **成果**: W51 (31) 與 W52 (46) 數值與 UI 完全對齊。
- **7D Rolling 分母實作**: 在 `cube_l5_task_periodic.js` 中成功導入 Dn 報表的 7 天滑動分母，解決週末失真問題。
- **業務規格對齊**: 完成指標順序與內容定義（1.1 & 1.2）的全面翻新。

## 🎯 專案當前狀態
- **基礎架構**: 已升級至 V3 Bitmap 架構，支援歷史數據回填。
- **穩定性**: W51/W52 已達成 100% 同步。
- **待辦**: 修正週/月報表的「過度聚合」問題。

## 待辦事項
- [x] 完成 V3 Bitmap DDL/DML 部署
- [x] 實作 7D Rolling 分母邏輯
- [/] 修正週/月報表的「Snapshot Point」取值邏輯 (待執行)
- [/] 診斷 W1 (NBU/E5) 12 筆數據的來源與定義
- [ ] 觀察長時間運行後的 Bitmap 聚合效能
