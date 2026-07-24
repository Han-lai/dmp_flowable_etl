#!/bin/bash
# ===========================================================
# DMP Flowable - Unified Data Pipeline Initialization
# (Supports Low-RAM/High-RAM mode)
# ===========================================================
set -e

# ---- 參數解析（時間窗一律用命令列參數帶入，不吃環境變數）----
# 用法: init_pipeline.sh [--low-ram|--high-ram] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
#   --low-ram (預設): 跑 Phase 1+2+3 (bronze + silver/gold)
#   --high-ram      : 只跑 Phase 1+2 (略過 silver/gold)
#   --start / --end : Phase 2 bronze 同步時間窗 (只影響 batch/fact 表)。
#                     --start 未給 = batch 表從 watermark 續跑；--end 未給 = 今天
MODE="--low-ram"
SYNC_START=""
SYNC_END=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --low-ram|--high-ram) MODE="$1"; shift ;;
        --start) SYNC_START="$2"; shift 2 ;;
        --end)   SYNC_END="$2"; shift 2 ;;
        --start=*) SYNC_START="${1#*=}"; shift ;;
        --end=*)   SYNC_END="${1#*=}"; shift ;;
        *) echo "Unknown argument: $1" >&2
           echo "Usage: $0 [--low-ram|--high-ram] [--start YYYY-MM-DD] [--end YYYY-MM-DD]" >&2
           exit 1 ;;
    esac
done
[[ -z "$SYNC_END" ]] && SYNC_END="$(date +%F)"

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
