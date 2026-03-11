#!/bin/bash
# ===========================================================
# DMP Flowable - 資料管線初始化腳本
# 用途: 全新部署時，依序建立 ClickHouse 資料表並同步 MSSQL 資料
#
# 使用方式:
#   chmod +x scripts/init_pipeline.sh
#   ./scripts/init_pipeline.sh
#
# 選項:
#   --dry-run   僅印出執行步驟，不實際執行
# ===========================================================

set -e  # 任何步驟失敗立即中止

DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "[DRY RUN 模式] 僅顯示執行步驟，不實際執行。"
fi

# --- 設定工作目錄為專案根目錄 ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"
echo "專案根目錄: $PROJECT_ROOT"

# --- 可選: 環境變數設定 (預設值已內建於 Python 腳本中) ---
export CLICKHOUSE_HOST="${CLICKHOUSE_HOST:-10.136.218.207}"
export CLICKHOUSE_PORT="${CLICKHOUSE_PORT:-8121}"
export CLICKHOUSE_USERNAME="${CLICKHOUSE_USERNAME:-default}"
export CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-default}"

echo ""
echo "=============================================="
echo " 步驟 1/2: 建立 Bronze / Silver / Gold 資料表"
echo "=============================================="
echo "執行: python scripts/etl/execute_etl.py"
echo "(此步驟會互動式確認已存在的表格，請依提示輸入 y 確認)"
echo ""

if [ "$DRY_RUN" = false ]; then
    python scripts/etl/execute_etl.py
    if [ $? -ne 0 ]; then
        echo "錯誤: execute_etl.py 執行失敗，請檢查 ClickHouse 連線。"
        exit 1
    fi
    echo "[完成] 所有資料表建立成功。"
fi

echo ""
echo "=============================================="
echo " 步驟 2/2: 同步 MSSQL 資料至 ClickHouse Bronze"
echo "=============================================="
echo "執行: python scripts/etl/sync_unified.py --table all"
echo "(首次執行時間較長，依資料量估計約 30~120 分鐘)"
echo ""

if [ "$DRY_RUN" = false ]; then
    python scripts/etl/sync_unified.py --table all
    if [ $? -ne 0 ]; then
        echo "錯誤: sync_unified.py 執行失敗，請檢查 JDBC Bridge 連線。"
        exit 1
    fi
    echo "[完成] MSSQL 資料同步成功。"
fi

echo ""
echo "=============================================="
echo " 初始化完成!"
echo " 下一步: 確認 API 服務是否正常"
echo "   curl http://${CLICKHOUSE_HOST}:7088/docs"
echo "=============================================="
