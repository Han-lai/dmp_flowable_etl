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
# MSSQL_PASSWORD defaults to "" in sync_unified_odbc.py if unset, which causes a silent
# ODBC login failure -> TRUNCATE succeeds but the following INSERT fails -> empty bronze
# tables (2026-06 incident). Fail loud here instead of letting Phase 2 wipe data quietly.
: "${MSSQL_PASSWORD:?MSSQL_PASSWORD must be set (empty value caused a bronze table wipe incident on 2026-06)}"
export CLICKHOUSE_HOST
export CLICKHOUSE_PORT="${CLICKHOUSE_PORT:-8121}"
export CLICKHOUSE_USERNAME="${CLICKHOUSE_USERNAME:-default}"
export CLICKHOUSE_PASSWORD
export MSSQL_PASSWORD

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
# (also rebuilds silver.mv_dim_mfg_five_level from freshly synced MDM tables, see sync_unified_odbc.py)
python scripts/etl/sync_unified_odbc.py --table all

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
