#!/usr/bin/env python3
"""
檢查 MSSQL 資料的時間範圍
"""

import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("🔍 檢查 MSSQL 資料時間範圍")
    print("=" * 80)
    
    # 檢查各表的時間範圍
    tables_to_check = [
        {
            'name': 'ACT_HI_IDENTITYLINK_0108',
            'mssql_table': 'APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0108',
            'time_column': 'CREATE_TIME_'
        },
        {
            'name': 'ACT_HI_TASKINST_0108',
            'mssql_table': 'APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108',
            'time_column': 'START_TIME_'
        },
        {
            'name': 'ACT_HI_PROCINST_0108',
            'mssql_table': 'APP_SRV_BPM.dbo.ACT_HI_PROCINST_0108',
            'time_column': 'START_TIME_'
        }
    ]
    
    for table_info in tables_to_check:
        print(f"\n📊 表格: {table_info['name']}")
        print("-" * 60)
        
        try:
            # 查詢 MSSQL 時間範圍
            range_sql = f"""
            SELECT 
                min_time, max_time, total_count
            FROM jdbc('mssql_master', '
                SELECT 
                    MIN({table_info['time_column']}) as min_time,
                    MAX({table_info['time_column']}) as max_time,
                    COUNT(*) as total_count
                FROM {table_info['mssql_table']}
                WHERE {table_info['time_column']} IS NOT NULL
            ')
            """
            
            print("正在查詢 MSSQL 時間範圍...")
            result = client.query(range_sql)
            
            if result.result_rows:
                min_time, max_time, total_count = result.result_rows[0]
                print(f"✅ MSSQL 時間範圍: {min_time} ~ {max_time}")
                print(f"✅ MSSQL 總筆數: {total_count:,}")
                
                # 計算時間跨度
                if min_time and max_time:
                    from datetime import datetime
                    min_dt = datetime.fromisoformat(str(min_time).replace('T', ' '))
                    max_dt = datetime.fromisoformat(str(max_time).replace('T', ' '))
                    days_span = (max_dt - min_dt).days
                    print(f"📅 時間跨度: {days_span} 天")
                
                # 查詢每年的資料分布
                print("\n📈 年度資料分布:")
                year_dist_sql = f"""
                SELECT year_data, count_data
                FROM jdbc('mssql_master', '
                    SELECT 
                        YEAR({table_info['time_column']}) as year_data,
                        COUNT(*) as count_data
                    FROM {table_info['mssql_table']}
                    WHERE {table_info['time_column']} IS NOT NULL
                    GROUP BY YEAR({table_info['time_column']})
                    ORDER BY year_data
                ')
                """
                
                year_result = client.query(year_dist_sql)
                for year, count in year_result.result_rows:
                    print(f"  {year}: {count:,} 筆")
                    
        except Exception as e:
            print(f"❌ 查詢失敗: {e}")

if __name__ == "__main__":
    main()