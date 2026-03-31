#!/bin/bash
# ===========================================================
# DMP Flowable - 統一資料管線初始化腳本 (相容 Low-RAM/High-RAM)
# ===========================================================
set -e

MODE=${1:-"--low-ram"}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$PROJECT_ROOT"

export CLICKHOUSE_HOST="${CLICKHOUSE_HOST:-10.136.218.207}"
export CLICKHOUSE_PORT="${CLICKHOUSE_PORT:-8121}"
export CLICKHOUSE_USERNAME="${CLICKHOUSE_USERNAME:-default}"
export CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-default}"

LOW_RAM_FLAG=""
if [[ "$MODE" == "--low-ram" ]]; then
    LOW_RAM_FLAG="--low-ram"
    echo "=============================================="
    echo "️ 啟動低記憶體防重載模式 (Low-RAM Safe Mode)"
    echo "=============================================="
else
    echo "=============================================="
    echo "啟動高規格極速模式 (High-RAM Fast Mode)"
    echo "=============================================="
fi

echo ""
echo "=== Phase 1: 建立 ClickHouse 地基結構 (Setup) =============================="
python scripts/etl/setup_schema.py

echo ""
echo "=== Phase 2: 全量同步外部資料 (MS SQL -> Bronze) ==========================="
# 使用 OOM 防護的 ODBC 引擎，支援自適應批次同步
python scripts/etl/sync_unified_odbc.py --table all

if [[ "$MODE" == "--low-ram" ]]; then
    echo ""
    echo "=== Phase 3: 啟動精確維度與事實計算引擎 (Backfill) ====================="
    # 使用升級後的統一運算引擎，支援斷點續傳與 OOM 保護
    python scripts/etl/execute_etl.py --backfill $LOW_RAM_FLAG
else
    # ================= HIGH-RAM =================
    echo ""
    echo "[提醒] 高規格模式下，ClickHouse 會在排程抵達時自動觸發 Silver/Gold 更新。"
    echo "[提醒] 高規格模式下，ClickHouse 會在排程抵達時自動觸發 Silver/Gold 更新。"
    echo "如果您急需立刻看到結果，也可以手動執行: "
    echo "python scripts/etl/execute_etl.py --backfill"
fi

echo ""
echo "=============================================="
echo "初始化管線全部完成!"
echo "下一步: 檢查應用端 API (curl http://${CLICKHOUSE_HOST}:7088/docs)"
echo "=============================================="
