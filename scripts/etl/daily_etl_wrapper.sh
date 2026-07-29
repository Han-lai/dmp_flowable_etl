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

# Fail loud on missing/empty credentials instead of letting downstream scripts silently
# wipe or fail to sync data. MSSQL_PASSWORD defaulting to "" caused a bronze table wipe
# incident on 2026-06 (this script runs unattended via cron with no human watching).
: "${CLICKHOUSE_HOST:?CLICKHOUSE_HOST must be set}"
: "${CLICKHOUSE_PASSWORD:?CLICKHOUSE_PASSWORD must be set}"
: "${MSSQL_PASSWORD:?MSSQL_PASSWORD must be set (empty value caused a bronze table wipe incident on 2026-06)}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting daily ETL sync..."

# 1. Incremental sync for Bronze layer (Auto-fetch based on watermark)
echo "-> [Step 1] Syncing Bronze from MSSQL..."
python scripts/etl/sync_unified_odbc.py --table all

# 2. Triggering Silver/Gold fact tables and metrics update (Unified Engine)
echo "-> [Step 2] Executing Silver/Gold Daily Compute..."
python scripts/etl/execute_etl.py --daily --low-ram

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ETL full-flow sync and computation completed."
