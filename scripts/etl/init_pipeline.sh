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
    echo " 啟動高規格極速模式 (High-RAM Fast Mode)"
    echo "=============================================="
fi

echo ""
echo "=== Phase 1: 建立 ClickHouse 空殼結構 ======================================"
python scripts/etl/execute_etl.py --skip-existing

echo ""
echo "=== Phase 2: 全量同步外部資料 (MS SQL -> Bronze) ==========================="
# ClickHouse Bronze 是純寫入，無 JOIN Overhead，全部一次拉完速度最快且不會 OOM。
# (註: sync_unified.py 內部已有 identitylink 每日批量拉取的記憶體保護機制)
python scripts/etl/sync_unified.py --table all

if [[ "$MODE" == "--low-ram" ]]; then
    echo ""
    echo "=== Phase 3: 啟動精確維度與事實計算引擎 (Phase 3 & 4) =================="
    # 使用我們全新開發的 Python 內嵌分批時間切割器，完美避開 OOM 與 Bash 解析錯誤
    # --start 預設為 2025-10-01 (您的資料正確起點)
    python scripts/etl/execute_etl.py --backfill $LOW_RAM_FLAG
else
    # ================= HIGH-RAM =================
    echo ""
    echo "[提醒] 高規格模式下，ClickHouse 會在排程抵達時自動觸發 Silver/Gold 更新。"
    echo "如果您急需立刻看到結果，也可以手動執行: "
    echo "python scripts/etl/execute_etl.py --backfill"
fi

echo ""
echo "=============================================="
echo " 初始化管線全部完成!"
echo "下一步: 檢查應用端 API (curl http://${CLICKHOUSE_HOST}:7088/docs)"
echo "=============================================="
