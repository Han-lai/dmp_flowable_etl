# Product Context

## 目標
建立 Flowable BPM 數據中台，將 MSSQL 資料同步至 ClickHouse，並透過 Cube.js 提供高效能指標查詢 API。

## 關鍵指標 (L5 任務執行完成率)
- **維度**: Plant, Factory, Line, VxType
- **指標**: 任務總數 (Total), 待辦 (Todo), 進行中 (Doing), 已完成 (Done)
- **指標**: 任務總數 (Total), 待辦 (Todo), 進行中 (Doing), 已完成 (Done)
- **邏輯**: 排除 Bypass=Y, 排除 E/C 開頭任務, 排除 Q/R 工單
- **ACC 邏輯**: **Cube 層**採用 7天滾動計算 (解決週末分母過小問題)；**SQL 層**維持每日快照。

## Cube 模型架構
- **標準版 (Standard)**: `cube_l5_task_periodic_v2.js`
    - 用途: 趨勢分析 (Trend Analysis), 寬表結構
    - ACC 邏輯: Month/Week 採用週期總量, Day 採用 7天滾動總量
- **轉置版 (Pivot)**: `cube_l5_task_periodic_v2_pivot.js`
    - 用途: 狀態比較 (Status Comparison), 長表結構 (Unpivot)
    - 特點: 支援時光機 (Time Machine) 回溯, 用以取代舊版 `cube_l5_task_completion.js`

## 驗證狀態
- **E5 線驗證 (WJ2/NBU)**: QAS 驗證結果 184 筆 (V3 Only). 該區無 V1 任務。
- **ST02 線驗證 (DG3/SMT)**: QAS 驗證結果 3636 筆 (V3 Only). 該區 V1 任務屬於 NPE 廠區。
- **結論**:
    - QAS 環境部分任務缺乏 `Region` 與 `lineName` 變數，需注意 Silver 層關聯風險。
    - V1 任務在 NBU/SMT 廠區未出現，主要集中在 NPE。

## 已知問題與解決方案
1. **Source 表版本管理**: UAT 環境使用 `_0108` 後綴表 (`ACT_HI_TASKINST_0108`)，ETL 已對接正確。
2. **QAS View 落差**: QAS 系統的 View 未更新，導致驗證時混淆。需請 DBA 更新。
2. **QAS View 落差**: QAS 系統的 View 未更新，導致驗證時混淆。需請 DBA 更新。
3. **時間篩選邏輯**: QAS 使用 `Start OR Claim OR End` 寬鬆邏輯，Gold 層使用 `Start Time` 嚴格邏輯。差異約 10% (180 vs 196)，屬預期內業務邏輯差異。
4. **ACC Rate 異常飆高 (已解決)**: 解決週末/連假期間因當日活動量 (`total_task`) 驟減導致 Acc Rate 暴飆的問題，已導入 Rolling 7 Days 分母邏輯。
5. **Superset 時間格式錯誤 (已解決)**: 解決 Dashboard 帶入微秒 Timestamp 導致的型別轉換錯誤，已於 V2 模型實作 Triple-OR 篩選。

## 重要文件
- [CLAUDE.md](../ARCHIVE/misc/CLAUDE.md): 專案狀態與技術備忘
- [investigation_reports/20260202_E4_Discrepancy_Report.md](../docs/investigation_reports/20260202_E4_Discrepancy_Report.md): E4 差異調查完整報告
