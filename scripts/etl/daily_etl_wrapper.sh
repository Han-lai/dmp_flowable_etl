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

# 2. 觸發 Silver/Gold 事實表與指標更新 (針對 207 最佳化架構)
echo "-> [Step 2] Executing Silver/Gold Daily Compute..."
python scripts/etl/execute_etl.py --daily

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ETL 全流程同步與計算完成。"
