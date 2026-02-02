#!/usr/bin/env python3
"""
Cube.js 依賴與 Gold 層更新腳本
==============================
1. 驗證 Cube.js 是否依賴 Gold 層快照表
2. 提供手動更新 Gold 層摘要表的功能
"""

import clickhouse_connect
import sys
import time
from datetime import datetime

# ClickHouse 連線設定
CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    print("=" * 80)
    print("📊 Cube.js 依賴與 Gold 層狀態檢查")
    print(f"   時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        print("✅ ClickHouse 連線成功\n")
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        sys.exit(1)

    # 1. 驗證 Cube.js 的資料來源表類型
    print("📋 1. Cube.js 資料來源驗證 (gold.l5_dashboard_summary)")
    print("-" * 80)
    
    check_sql = """
    SELECT database, name, engine, total_rows, metadata_modification_time
    FROM system.tables 
    WHERE database = 'gold' AND name = 'l5_dashboard_summary'
    """
    result = client.query(check_sql)
    
    if result.result_rows:
        db, name, engine, rows, modified = result.result_rows[0]
        print(f"表名: {db}.{name}")
        print(f"引擎: {engine}")
        print(f"目前筆數: {rows:,}")
        print(f"最後結構修改時間: {modified}")
        
        if "MaterializedView" in engine:
            print("\n💡 結論: 這是【自動更新】的 Materialized View。")
        else:
            print("\n💡 結論: Cube.js 目前依賴的是【實體快照表】。")
            print("   這表示資料需要透過 INSERT 命令手動或定時更新，不會隨 Bronze 層即時變動。")
    else:
        print("❌ 找不到 gold.l5_dashboard_summary 表")

    print("\n" + "-" * 80)
    
    # 2. 檢查資料新鮮度
    print("📋 2. 資料新鮮度 (最後資料更新時間)")
    try:
        freshness = client.command("SELECT max(_update_time) FROM gold.l5_dashboard_summary")
        print(f"Gold 層最後資料時間: {freshness}")
    except:
        print("無法取得更新時間")

    print("\n" + "=" * 80)
    print("🚀 如需【手動更新】Gold 層快照，請執行以下命令：")
    print("-" * 80)
    print("python scripts/etl/update_gold_layer.py")
    print("=" * 80)

if __name__ == "__main__":
    main()
