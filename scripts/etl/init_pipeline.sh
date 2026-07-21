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

: "${MSSQL_PASSWORD:?MSSQL_PASSWORD must be set (empty value caused a bronze table wipe incident on 2026-06)}"
export CLICKHOUSE_HOST
export CLICKHOUSE_PORT="${CLICKHOUSE_PORT:-8121}"
export CLICKHOUSE_USERNAME="${CLICKHOUSE_USERNAME:-default}"
export CLICKHOUSE_PASSWORD
export MSSQL_PASSWORD
SYNC_CONFIG="${SYNC_CONFIG:-sync_tables.yaml}"
# 對齊 sync_tables.yaml 的 history_start；更早的區間 Bronze 無資料，只會空跑整欄掃描
BACKFILL_START="${BACKFILL_START:-2025-10-01}"
BACKFILL_END="${BACKFILL_END:-$(date +%F)}"

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
echo "--- Sync config: $SYNC_CONFIG | Backfill window: $BACKFILL_START ~ $BACKFILL_END"

echo ""
echo "=== Phase 1: Setting up ClickHouse base schema =============================="
python scripts/etl/setup_schema.py

echo ""
echo "=== Phase 2: Full sync from external data (MSSQL -> Bronze) ==========================="
echo "    Using sync config: $SYNC_CONFIG"
# Using OOM-protected ODBC engine with adaptive batch sync support
# (also rebuilds silver.mv_dim_mfg_five_level from freshly synced MDM tables, see sync_unified_odbc.py)
python scripts/etl/sync_unified_odbc.py --table all --config "$SYNC_CONFIG"

if [[ "$MODE" == "--low-ram" ]]; then
    echo ""
    echo "=== Phase 3: Starting precise dimension and fact calculation engine (Backfill) ====================="
    echo "    Backfill window: $BACKFILL_START ~ $BACKFILL_END"
    # Using upgraded unified compute engine with checkpointing and OOM protection
    python scripts/etl/execute_etl.py --backfill $LOW_RAM_FLAG --start "$BACKFILL_START" --end "$BACKFILL_END"
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
