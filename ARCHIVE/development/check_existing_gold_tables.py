#!/usr/bin/env python3
"""
檢查現有的 ClickHouse Gold 層表格，用於建立 L5 Dashboard Data Model
"""

import clickhouse_connect
from datetime import datetime

def check_gold_tables():
    """檢查 Gold 層所有表格"""
    
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
        print("=" * 80)
        
        # 檢查 Gold 層所有表格
        tables_query = """
        SELECT 
            name,
            engine,
            total_rows,
            total_bytes
        FROM system.tables 
        WHERE database = 'gold' 
        ORDER BY name
        """
        
        result = client.query(tables_query)
        
        if result.result_rows:
            print("📊 Gold 層現有表格:")
            print("-" * 80)
            for row in result.result_rows:
                name, engine, rows, bytes_size = row
                print(f"   {name:<50} | {engine:<20} | {rows:>10,} rows | {bytes_size:>10,} bytes")
            
            print("\n" + "=" * 80)
            
            # 重點檢查 L5 相關表格
            l5_tables = [
                'DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV',
                'DAILY_L5_TASK_COMPLETION_SNAPSHOT',
                'L5_TASK_COMPLETION_SNAPSHOT_MV'
            ]
            
            print("🎯 L5 相關表格詳細資訊:")
            print("-" * 80)
            
            for table_name in l5_tables:
                # 檢查表格是否存在
                check_query = f"""
                SELECT COUNT(*) as exists
                FROM system.tables 
                WHERE database = 'gold' AND name = '{table_name}'
                """
                
                exists_result = client.query(check_query)
                if exists_result.result_rows[0][0] > 0:
                    print(f"\n✅ {table_name}")
                    
                    # 檢查表格結構
                    desc_query = f"DESCRIBE gold.{table_name}"
                    desc_result = client.query(desc_query)
                    
                    print("   欄位結構:")
                    for desc_row in desc_result.result_rows:
                        col_name, col_type = desc_row[0], desc_row[1]
                        print(f"     {col_name:<30} | {col_type}")
                    
                    # 檢查資料範圍
                    try:
                        range_query = f"""
                        SELECT 
                            MIN(snapshot_date) as min_date,
                            MAX(snapshot_date) as max_date,
                            COUNT(*) as total_rows,
                            COUNT(DISTINCT snapshot_date) as date_count
                        FROM gold.{table_name}
                        """
                        range_result = client.query(range_query)
                        if range_result.result_rows:
                            min_date, max_date, total_rows, date_count = range_result.result_rows[0]
                            print(f"   資料範圍: {min_date} ~ {max_date}")
                            print(f"   總筆數: {total_rows:,}")
                            print(f"   日期數: {date_count}")
                    except Exception as e:
                        print(f"   資料範圍查詢失敗: {e}")
                    
                    # 檢查維度欄位
                    try:
                        sample_query = f"""
                        SELECT *
                        FROM gold.{table_name}
                        LIMIT 1
                        """
                        sample_result = client.query(sample_query)
                        if sample_result.result_rows:
                            print("   範例資料 (第一筆):")
                            columns = [col[0] for col in desc_result.result_rows]
                            sample_data = sample_result.result_rows[0]
                            for i, (col, val) in enumerate(zip(columns, sample_data)):
                                if i < 10:  # 只顯示前10個欄位
                                    print(f"     {col}: {val}")
                            if len(columns) > 10:
                                print(f"     ... 還有 {len(columns) - 10} 個欄位")
                    except Exception as e:
                        print(f"   範例資料查詢失敗: {e}")
                        
                else:
                    print(f"\n❌ {table_name} - 不存在")
            
        else:
            print("❌ Gold 層沒有找到任何表格")
            
    except Exception as e:
        print(f"❌ 連接錯誤: {e}")
        return False
        
    return True

if __name__ == "__main__":
    check_gold_tables()