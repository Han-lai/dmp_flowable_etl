#!/bin/bash
# ===========================================================
# DMP Flowable - Unified Data Pipeline Initialization
# (Supports Low-RAM/High-RAM mode)
# ===========================================================
set -e

MODE=${1:-"--low-ram"}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$PROJECT_ROOT"

: "${CLICKHOUSE_HOST:?CLICKHOUSE_HOST must be set}"
: "${CLICKHOUSE_PASSWORD:?CLICKHOUSE_PASSWORD must be set}"
export CLICKHOUSE_HOST
export CLICKHOUSE_PORT="${CLICKHOUSE_PORT:-8121}"
export CLICKHOUSE_USERNAME="${CLICKHOUSE_USERNAME:-default}"
export CLICKHOUSE_PASSWORD

LOW_RAM_FLAG=""
if [[ "$MODE" == "--low-ram" ]]; then
    LOW_RAM_FLAG="--low-ram"
    echo "=============================================="
    echo " Starting Low-RAM Safe Mode"
    echo "=============================================="
else
    echo "=============================================="
    echo " Starting High-RAM Performance Mode"
    echo "=============================================="
fi

echo ""
echo "=== Phase 1: Setting up ClickHouse base schema =============================="
python scripts/etl/setup_schema.py

echo ""
echo "=== Phase 2: Full sync from external data (MSSQL -> Bronze) ==========================="
# Using OOM-protected ODBC engine with adaptive batch sync support
python scripts/etl/sync_unified_odbc.py --table all

echo ""
echo "=== Phase 2.5: Populate MDM-dependent dimension table (mv_dim_mfg_five_level) ==="
# Must run after Bronze sync: this table's source data (bronze.common_mdm_*) only exists post-sync
python scripts/etl/setup_schema.py --file sql/etl/dml/init_dim_mfg_five_level.sql

if [[ "$MODE" == "--low-ram" ]]; then
    echo ""
    echo "=== Phase 3: Starting precise dimension and fact calculation engine (Backfill) ====================="
    # Using upgraded unified compute engine with checkpointing and OOM protection
    python scripts/etl/execute_etl.py --backfill $LOW_RAM_FLAG
else
    # ================= HIGH-RAM =================
    echo ""
    echo "[Reminder] In High-RAM mode, ClickHouse automatically triggers Silver/Gold updates upon schedule."
    echo "If you need immediate results, you can execute manually: "
    echo "python scripts/etl/execute_etl.py --backfill"
fi

echo ""
echo "=============================================="
echo " Pipeline initialization complete!"
echo " Next step: Check application API (curl http://${CLICKHOUSE_HOST}:7088/docs)"
echo "=============================================="
