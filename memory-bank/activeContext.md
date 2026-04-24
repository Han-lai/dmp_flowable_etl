# 當前工作脈絡 (Active Context)

**最後更新**: 2026-04-24

---

## 🎯 當前焦點 (Current Focus)

### ✅ 近期已解決 (2026-04-24 穩定化里程碑)
- **週/月報表數據偏移修正 (V3.2 Final)**: 
    - 已解決 `UNION ALL` 導致的區間過度聚合問題。
    - 採用 **「期末單日快照 (Period-End Snapshot)」** 取值邏輯，確保週、月報表反映的是該週期最後一刻的狀態。
- **Superset 下拉選單效能危機**:
    - 透過實作 **`DimMfgFilter` 專用 Cube**，將原本 >60s 的選單載入優化至 **<0.1s**。
- **ClickHouse 24.3 相容性問題**:
    - 解決了 ISO Date String (`T00:00:00Z`) 導致的轉換噴錯問題。
    - 實作了 **String-based Filtering 模式**，改用 `YYYY-MM-DD` 10 位字串進行精準比對。
- **數據對齊 (W1 跨年週)**:
    - 已驗證 W1 在跨年期間的 Bitmap 運算正確性，達成 100% 同步。

### ⏩ 進行中
- **自動化監控**: 觀察長週期 (超過 6 個月) 數據在 V3 Bitmap 聚合下的查詢效能。
- **維護 SOP**: 完善基於 `DimMfgFilter` 的新篩選器配置指南。

## 🎯 專案當前狀態
- **整體架構**: 已全面切換至 **V3 Bitmap 穩定版**。
- **展示層**: Superset 儀表板已進入穩定運行期，支援 0.1s 極速過濾與 11-period 回溯檢視。
- **代碼同步**: 本地 Cube 模型、ETL SQL 與 GitLab 遠端倉庫已完成同步 (`f39e37e`)。

## 待辦事項
- [x] 完成 V3 Bitmap DDL/DML 部署
- [x] 實作 7D Rolling 分母邏輯
- [x] 完成技術設計規格書 (TDD v4.0) 正式化
- [x] 修正週/月報表的「Snapshot Point」取值邏輯
- [x] 診斷 W1 (NBU/E5) 數據對齊
- [x] 解決 ClickHouse 24.3 與 Superset ISO Date 的轉型報錯
- [x] 優化 Superset 下拉選單效能 (DimMfgFilter)
- [ ] 觀察長時間運行後的 Bitmap 聚合效能 (持續中)
- [ ] 實作 L7 人員利用率數據管線
