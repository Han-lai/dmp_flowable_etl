@echo off
echo ========================================
echo ClickHouse MVIEW 重建執行腳本
echo ========================================

echo 正在執行 MVIEW 重建...
clickhouse-client --query "$(type sql\REBUILD_ALL_MVIEWS.sql)"

if %ERRORLEVEL% EQU 0 (
    echo ✅ MVIEW 重建完成
) else (
    echo ❌ MVIEW 重建失敗
)

pause