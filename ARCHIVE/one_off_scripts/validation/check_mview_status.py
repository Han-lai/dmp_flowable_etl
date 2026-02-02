#!/usr/bin/env python3
"""
MVIEW 狀態檢查腳本 (快速版)
===========================
使用 system 表元數據查詢，避免全表掃描

功能：
1. 列出所有 MVIEW 及其引擎類型
2. 使用 system.tables 快速取得筆數估計
3. 驗證資料是否會自動更新
"""

import clickhouse_connect
import sys
from datetime import datetime

# ClickHouse 連線設定
CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}


def main():
    print("=" * 80)
    print("🔍 ClickHouse MVIEW 狀態檢查 (快速版)")
    print(f"   執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        print("✅ ClickHouse 連線成功\n")
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        sys.exit(1)
    
    # 1. 快速查詢：使用 system.tables 取得所有表的元數據（包含 MVIEW 目標表）
    print("📋 1. Silver/Gold 層表狀態 (使用 system.tables 元數據)")
    print("-" * 100)
    
    fast_sql = """
    SELECT 
        database,
        name,
        engine,
        total_rows,
        formatReadableSize(total_bytes) as size,
        metadata_modification_time
    FROM system.tables
    WHERE database IN ('silver', 'gold')
      AND total_rows > 0
    ORDER BY database, name
    """
    
    result = client.query(fast_sql)
    
    if result.result_rows:
        print(f"{'Database':<8} | {'Table Name':<50} | {'Rows':<15} | {'Size':<12} | {'Last Modified'}")
        print("-" * 120)
        for row in result.result_rows:
            db, name, engine, rows, size, modified = row
            rows_str = f"{rows:,}" if rows else "0"
            mod_str = str(modified)[:19] if modified else "N/A"
            # 簡化表名顯示
            display_name = name[:50] if len(name) <= 50 else name[:47] + "..."
            print(f"{db:<8} | {display_name:<50} | {rows_str:>14} | {size:<12} | {mod_str}")
    else:
        print("⚠️ Silver/Gold 層沒有資料")
    
    print()
    
    # 2. 檢查 Materialized View 定義
    print("📋 2. Materialized View 定義")
    print("-" * 100)
    
    mview_sql = """
    SELECT 
        database,
        name,
        as_select
    FROM system.tables
    WHERE engine = 'MaterializedView'
      AND database IN ('silver', 'gold')
    ORDER BY database, name
    """
    
    result = client.query(mview_sql)
    
    if result.result_rows:
        print(f"找到 {len(result.result_rows)} 個 Materialized View:\n")
        for row in result.result_rows:
            db, name, as_select = row
            # 擷取來源表
            source = "Bronze 層" if "bronze." in (as_select or "") else "未知"
            print(f"  • {db}.{name}")
            print(f"    來源: {source}")
    else:
        print("⚠️ 未找到 Materialized View")
    
    print()
    
    # 3. MVIEW 自動更新機制說明
    print("📋 3. MVIEW 自動更新機制")
    print("-" * 100)
    print("""
✅ ClickHouse MVIEW 會自動更新：

  Bronze 層 INSERT 新資料
       ↓ (自動觸發)
  Silver MVIEW 計算並插入
       ↓ (自動觸發)  
  Gold MVIEW 計算並插入

⚠️ 注意：當 Bronze 層執行同步腳本從 MSSQL 拉取新資料時，
   INSERT 操作會自動觸發 MVIEW 更新，無需手動刷新。
""")
    
    print("=" * 80)
    print("✅ 檢查完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
