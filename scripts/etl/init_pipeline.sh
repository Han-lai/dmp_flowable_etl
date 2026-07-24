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
# 對齊 sync_tables.yaml 的 history_start；execute_etl.py 的預設 2025-01-01 比 bronze
# 實際資料起點早九個月，會空跑大量窗格
BACKFILL_START="${BACKFILL_START:-2025-10-01}"

# Phase 2 Bronze 同步時間窗（只影響 batch 策略的 fact 表；full 維度表照常整表同步）。
# SYNC_START 空 = 不帶 --start，batch 表從 watermark 續跑（等同現狀）。
# SYNC_START 有值 = 從該日起按 step_days 自動切窗拉取，不再無邊界一次 all。
SYNC_START="${SYNC_START:-}"
SYNC_END="${SYNC_END:-$(date +%F)}"

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
# 帶時間窗：batch 表按 --start/--end 自動切成 step_days 小批拉取，降低單批 MSSQL 峰值。
SYNC_ARGS=(--table all --end "$SYNC_END")
[[ -n "$SYNC_START" ]] && SYNC_ARGS+=(--start "$SYNC_START")
echo "    Sync window: ${SYNC_START:-<from watermark>} -> $SYNC_END"
python scripts/etl/sync_unified_odbc.py "${SYNC_ARGS[@]}"

if [[ "$MODE" == "--low-ram" ]]; then
    echo ""
    echo "=== Phase 3: Starting precise dimension and fact calculation engine (Backfill) ====================="
    echo "    Backfill from: $BACKFILL_START"
    # Using upgraded unified compute engine with checkpointing and OOM protection
    python scripts/etl/execute_etl.py --backfill $LOW_RAM_FLAG --start "$BACKFILL_START"
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
echo "=============================================="
