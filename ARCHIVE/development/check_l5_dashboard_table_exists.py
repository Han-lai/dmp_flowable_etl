#!/usr/bin/env python3
"""
檢查 L5 Dashboard 彙總表是否存在於 ClickHouse 中
"""

import clickhouse_connect
import sys
from datetime import datetime

def check_table_exists():
    """檢查 gold.L5_DASHBOARD_COMPLETION_SUMMARY_MV 是否存在"""
    
    try:
        # 連接 ClickHouse
        client = clickhouse_connect.get_client(
            host='10.136.218.207',
            port=8121,
            username='default',
            password='default',
            database='default'
        )
        
        print(f"🔍 檢查時間: {datetime.now()}")
        print("=" * 60)
        
        # 檢查表格是否存在
        check_query = """
        SELECT 
            database,
            name,
            engine,
            create_table_query
        FROM system.tables 
        WHERE database = 'gold' 
          AND name = 'L5_DASHBOARD_COMPLETION_SUMMARY_MV'
        """
        
        result = client.query(check_query)
        
        if result.result_rows:
            print("✅ 表格存在:")
            for row in result.result_rows:
                print(f"   Database: {row[0]}")
                print(f"   Table: {row[1]}")
                print(f"   Engine: {row[2]}")
                print(f"   Create Query: {row[3][:100]}...")
            
            # 檢查資料筆數
            count_query = "SELECT COUNT(*) FROM gold.L5_DASHBOARD_COMPLETION_SUMMARY_MV"
            count_result = client.query(count_query)
            print(f"   資料筆數: {count_result.result_rows[0][0]:,}")
            
            # 檢查最新資料日期
            date_query = """
            SELECT 
                MIN(snapshot_date) as min_date,
                MAX(snapshot_date) as max_date,
                COUNT(DISTINCT snapshot_date) as date_count
            FROM gold.L5_DASHBOARD_COMPLETION_SUMMARY_MV
            """
            date_result = client.query(date_query)
            if date_result.result_rows:
                min_date, max_date, date_count = date_result.result_rows[0]
                print(f"   日期範圍: {min_date} ~ {max_date} ({date_count} 天)")
            
        else:
            print("❌ 表格不存在: gold.L5_DASHBOARD_COMPLETION_SUMMARY_MV")
            print("\n📋 需要執行的步驟:")
            print("1. 執行 sql/create_l5_dashboard_completion_table.sql")
            print("2. 重啟 Cube.js 服務")
            
        print("=" * 60)
        
        # 檢查相關的視圖是否存在
        view_query = """
        SELECT name, engine
        FROM system.tables 
        WHERE database = 'gold' 
          AND name IN ('vw_l5_dashboard_completion', 'vw_l5_dashboard_charts')
        """
        
        view_result = client.query(view_query)
        if view_result.result_rows:
            print("📊 相關視圖:")
            for row in view_result.result_rows:
                print(f"   {row[0]} ({row[1]})")
        else:
            print("❌ 相關視圖不存在")
            
    except Exception as e:
        print(f"❌ 連接錯誤: {e}")
        return False
        
    return len(result.result_rows) > 0 if 'result' in locals() else False

if __name__ == "__main__":
    exists = check_table_exists()
    sys.exit(0 if exists else 1)