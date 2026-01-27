#!/bin/bash
# ========================================
# ClickHouse MVIEW 重建執行腳本
# ========================================

echo "========================================"
echo "ClickHouse MVIEW 重建執行腳本"
echo "========================================"

echo "正在執行 MVIEW 重建..."
clickhouse-client < sql/REBUILD_ALL_MVIEWS.sql

if [ $? -eq 0 ]; then
    echo "✅ MVIEW 重建完成"
else
    echo "❌ MVIEW 重建失敗"
fi