# 專案概述 - DMP Flowable

## 專案名稱
DMP Flowable 資料同步專案

## 目標
將 MSSQL 的 Flowable BPM 資料同步到 ClickHouse，建立 Bronze/Silver/Gold 層資料倉儲，並透過 Cube.js 提供 API。

## 核心功能
1. **資料同步**: MSSQL → ClickHouse (原生 ODBC 驅動，支援 18 張表，Adaptive Batching)
2. **資料轉換**: Bronze → Silver → Gold 三層物理化架構 (ReplacingMergeTree 引擎)
3. **指標計算**: L5 任務完成率、人員使用率等 (支援 15 個月歷史數據)
4. **API 服務**: Cube.js 語意層 API + FastAPI 報表 API

## 專案狀態
🟢 **已完成 (穩定)** - 已從 JDBC Bridge 遷移至原生 ODBC 管線，並在 Server 76 穩定運作（低記憶體模式）。
🟢 **資料對齊 (驗證)** - 完成 HR Employee 姓名補全，與來源端 MSSQL 達到 100% 資料對齊。

## 維護者資訊
- 使用 ClickHouse 25.x (Server 76, 6GB RAM)
- 使用 Cube.js 作為語意層
- 使用 Python 腳本進行排程管理 (`sync_unified_odbc.py`, `execute_etl.py`)
