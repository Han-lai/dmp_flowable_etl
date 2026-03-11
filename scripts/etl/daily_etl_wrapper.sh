#!/bin/bash
# ===========================================================
# DMP Flowable - 每日增量同步腳本 (Daily ETL Wrapper)
# 用途: 用於日常定期排程，僅同步增量資料並刷新 View
# ===========================================================

# 任何步驟失敗立即中止
set -e

# 切換到腳本所在目錄的父目錄 (專案根目錄)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 開始執行每日 ETL 同步..."

# 1. 增量同步 Bronze 層 (自動根據 Watermark 抓取)
echo "-> [Step 1] Syncing Bronze from MSSQL..."
python scripts/etl/sync_unified.py --table all

# 2. 刷新 Silver/Gold 層視圖
# (大部分 Materialized View 設有 Refreshable 屬性會自動更新，
# 若需要立即強制更新，可在此加入 SYSTEM REFRESH 語句)
# echo "-> [Step 2] Triggering manual refresh if needed..."
# clickhouse-client --query "SYSTEM REFRESH VIEW gold.mv_l5_task_completion;"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ETL 同步完成。"
