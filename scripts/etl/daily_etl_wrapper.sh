#!/bin/bash
# ===========================================================
# DMP Flowable - Daily Incremental Sync Script (Daily ETL Wrapper)
# Purpose: Daily scheduled sync, incremental data only and view refresh.
# ===========================================================

# Abort immediately if any step fails
set -e

# Change to project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting daily ETL sync..."

# 1. Incremental sync for Bronze layer (Auto-fetch based on watermark)
echo "-> [Step 1] Syncing Bronze from MSSQL..."
python scripts/etl/sync_unified_odbc.py --table all

# 2. Triggering Silver/Gold fact tables and metrics update (Unified Engine)
echo "-> [Step 2] Executing Silver/Gold Daily Compute..."
python scripts/etl/execute_etl.py --daily --low-ram

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ETL full-flow sync and computation completed."
