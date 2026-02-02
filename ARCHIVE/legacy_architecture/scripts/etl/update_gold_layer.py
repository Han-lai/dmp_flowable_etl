#!/usr/bin/env python3
"""
Gold 層手動更新腳本
====================
此腳本會將 Silver 層的最新計算結果刷新進入 Gold 層快照表 (gold.l5_dashboard_summary)
"""

import clickhouse_connect
import sys
import time
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
    print("🔄 正在更新 Gold 層快照 (snapshot_date, region, plant, ...) ")
    print(f"   開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        
        print("1. 清空舊快照 (TRUNCATE)...")
        client.command("TRUNCATE TABLE gold.l5_dashboard_summary")
        
        print("2. 從 Silver MVIEW 計算並填入新資料 (INSERT)...")
        start_time = time.perf_counter()
        
        insert_sql = """
        INSERT INTO gold.l5_dashboard_summary
        SELECT * FROM gold.v_l5_dashboard_summary_populate
        """
        client.command(insert_sql)
        
        duration = time.perf_counter() - start_time
        
        # 取得更新後筆數
        count = client.command("SELECT count(*) FROM gold.l5_dashboard_summary")
        
        print(f"\n✅ 更新完成！")
        print(f"   耗時: {duration:.2f} 秒")
        print(f"   總筆數: {count:,}")
        
    except Exception as e:
        print(f"\n❌ 更新失敗: {e}")
        sys.exit(1)

    print("=" * 80)

if __name__ == "__main__":
    main()
