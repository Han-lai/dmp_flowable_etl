# Product Context

## 目標
建立 Flowable BPM 數據中台，將 MSSQL 資料同步至 ClickHouse，並透過 Cube.js 提供高效能指標查詢 API。

## 關鍵指標 (L5 任務執行完成率)
- **維度**: Plant, Factory, Line, VxType
- **指標**: 任務總數 (Total), 待辦 (Todo), 進行中 (Doing), 已完成 (Done)
- **邏輯**: 排除 Bypass=Y, 排除 E/C 開頭任務, 排除 Q/R 工單

## 驗證狀態
- **E5 線驗證**: ClickHouse (196筆) 與 QAS 手動查詢 (198筆) 吻合。
- **E4 線驗證**: 
    - ClickHouse (163筆) 反映真實 Source (`ACT_HI_TASKINST_0108`) 數據。
    - QAS View (5筆) 因指向舊表而顯示錯誤數據。
    - **結論**: 信任 ClickHouse 數據。

## 已知問題與解決方案
1. **Source 表版本管理**: UAT 環境使用 `_0108` 後綴表 (`ACT_HI_TASKINST_0108`)，ETL 已對接正確。
2. **QAS View 落差**: QAS 系統的 View 未更新，導致驗證時混淆。需請 DBA 更新。
3. **時間篩選邏輯**: QAS 使用 `Start OR Claim OR End` 寬鬆邏輯，Gold 層使用 `Start Time` 嚴格邏輯。差異約 10% (180 vs 196)，屬預期內業務邏輯差異。

## 重要文件
- [CLAUDE.md](../ARCHIVE/misc/CLAUDE.md): 專案狀態與技術備忘
- [investigation_reports/20260202_E4_Discrepancy_Report.md](../docs/investigation_reports/20260202_E4_Discrepancy_Report.md): E4 差異調查完整報告
