#!/bin/bash
# ===========================================================
# DMP Flowable - Unified Data Pipeline Initialization
# (Supports Low-RAM/High-RAM mode)
# -----------------------------------------------------------
# 範例:
#   ./init_pipeline.sh                                                  # 完整初始化 (Phase 1+2+3)
#   ./init_pipeline.sh --phase 1                                        # 只部署 schema
#   ./init_pipeline.sh --phase 2 --start 2026-04-01 --end 2026-04-30    # 只同步 4 月 bronze
#   ./init_pipeline.sh --phase 3 --start 2026-04-01 --end 2026-04-30    # 只回填 4 月 silver/gold
#   ./init_pipeline.sh --phase 2,3 --start 2026-05-01 --end 2026-05-31  # 5 月同步 + 回填
#
# 逐月回填（每次換一組起訖，依時間順序跑）:
#   ./init_pipeline.sh --phase 2,3 --start 2026-03-01 --end 2026-03-31
#   ./init_pipeline.sh --phase 2,3 --start 2026-04-01 --end 2026-04-30
#   ./init_pipeline.sh --phase 2,3 --start 2026-05-01 --end 2026-05-31
#   注意: execute_etl.py 會 skip 已標記 SUCCESS 的相同視窗，重跑同一組起訖不會有作用。
# ===========================================================
set -e

# ---- 參數解析（時間窗一律用命令列參數帶入，不吃環境變數）----
#   --phase       1=schema 部署  2=MSSQL→Bronze 同步  3=Silver/Gold 回填（逗號分隔，預設全跑）
#   --start/--end Phase 2 當同步窗、Phase 3 當回填運算窗
#                 未給 start: Phase 2 走 watermark、Phase 3 用 BACKFILL_START；未給 end: 今天
#   --high-ram    略過 Phase 3（預設 --low-ram）
USAGE="Usage: $0 [--low-ram|--high-ram] [--phase N[,N...]] [--start YYYY-MM-DD] [--end YYYY-MM-DD]"
MODE="--low-ram"
WINDOW_START=""
WINDOW_END=""
PHASES="1,2,3"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --low-ram|--high-ram) MODE="$1"; shift ;;
        --phase) PHASES="$2"; shift 2 ;;
        --start) WINDOW_START="$2"; shift 2 ;;
        --end)   WINDOW_END="$2"; shift 2 ;;
        --phase=*) PHASES="${1#*=}"; shift ;;
        --start=*) WINDOW_START="${1#*=}"; shift ;;
        --end=*)   WINDOW_END="${1#*=}"; shift ;;
        *) echo "Unknown argument: $1" >&2
           echo "$USAGE" >&2
           exit 1 ;;
    esac
done
SYNC_START="$WINDOW_START"
SYNC_END="${WINDOW_END:-$(date +%F)}"

# 逗號清單比對，前後補逗號避免 1 誤命中 21
has_phase(){ [[ ",$PHASES," == *",$1,"* ]]; }

if ! has_phase 1 && ! has_phase 2 && ! has_phase 3; then
    echo "Error: --phase '$PHASES' 未包含任何有效階段 (1/2/3)" >&2
    echo "$USAGE" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$PROJECT_ROOT"

: "${CLICKHOUSE_HOST:?CLICKHOUSE_HOST must be set}"
: "${CLICKHOUSE_PASSWORD:?CLICKHOUSE_PASSWORD must be set}"


if has_phase 2; then
    : "${MSSQL_PASSWORD:?MSSQL_PASSWORD must be set (empty value caused a bronze table wipe incident on 2026-06)}"
    export MSSQL_PASSWORD
fi
export CLICKHOUSE_HOST
export CLICKHOUSE_PORT="${CLICKHOUSE_PORT:-8121}"
export CLICKHOUSE_USERNAME="${CLICKHOUSE_USERNAME:-default}"
export CLICKHOUSE_PASSWORD
BACKFILL_START="${WINDOW_START:-${BACKFILL_START:-2025-10-01}}"
BACKFILL_END="$WINDOW_END"

LOW_RAM_FLAG=""
[[ "$MODE" == "--low-ram" ]] && LOW_RAM_FLAG="--low-ram"
echo "=============================================="
if [[ "$MODE" == "--low-ram" ]]; then
    echo " Starting Low-RAM Safe Mode"
else
    echo " Starting High-RAM Performance Mode"
fi
echo "=============================================="

echo "    Phases to run: $PHASES"

if has_phase 1; then
    echo ""
    echo "=== Phase 1: Setting up ClickHouse base schema =============================="
    python scripts/etl/setup_schema.py
fi

if has_phase 2; then
    echo ""
    echo "=== Phase 2: Full sync from external data (MSSQL -> Bronze) ==========================="

    SYNC_ARGS=(--table all --end "$SYNC_END")
    [[ -n "$SYNC_START" ]] && SYNC_ARGS+=(--start "$SYNC_START")
    echo "    Sync window: ${SYNC_START:-<from watermark>} -> $SYNC_END"
    python scripts/etl/sync_unified_odbc.py "${SYNC_ARGS[@]}"
fi

if has_phase 3; then
    if [[ "$MODE" == "--low-ram" ]]; then
        echo ""
        echo "=== Phase 3: Starting precise dimension and fact calculation engine (Backfill) ====================="
        echo "    Backfill window: $BACKFILL_START -> ${BACKFILL_END:-<today, execute_etl.py default>}"
        # Using upgraded unified compute engine with checkpointing and OOM protection
        BACKFILL_ARGS=(--backfill $LOW_RAM_FLAG --start "$BACKFILL_START")
        [[ -n "$BACKFILL_END" ]] && BACKFILL_ARGS+=(--end "$BACKFILL_END")
        python scripts/etl/execute_etl.py "${BACKFILL_ARGS[@]}"
    else
        # ================= HIGH-RAM =================
        echo ""
        echo "[Reminder] In High-RAM mode, ClickHouse automatically triggers Silver/Gold updates upon schedule."
        echo "If you need immediate results, you can execute manually: "
        echo "python scripts/etl/execute_etl.py --backfill"
    fi
fi

echo ""
echo "=============================================="
echo " Pipeline initialization complete!"
echo "=============================================="
