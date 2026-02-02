#!/usr/bin/env python3
"""
檢查 ACT_HI_VARINST_0108 表的資料範圍和分布
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
    
    print("🔍 檢查 ACT_HI_VARINST_0108 資料範圍")
    print("=" * 80)
    
    try:
        # 檢查 MSSQL 資料總量
        count_sql = """
        SELECT count(*) FROM jdbc('mssql_master', '
            SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108
        ')
        """
        
        total_count = client.command(count_sql)
        print(f"MSSQL 總筆數: {total_count:,}")
        
        # 檢查時間範圍 (假設有 CREATE_TIME_ 欄位)
        print("\n🕐 檢查時間範圍:")
        print("-" * 60)
        
        # 先檢查表結構，看有什麼時間欄位
        structure_sql = """
        SELECT column_name FROM jdbc('mssql_master', '
            SELECT COLUMN_NAME as column_name
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = ''ACT_HI_VARINST_0108''
              AND TABLE_SCHEMA = ''dbo''
              AND (COLUMN_NAME LIKE ''%TIME%'' OR COLUMN_NAME LIKE ''%DATE%'')
            ORDER BY ORDINAL_POSITION
        ')
        """
        
        try:
            time_columns = client.query(structure_sql)
            print("發現時間相關欄位:")
            for row in time_columns.result_rows:
                print(f"  - {row[0]}")
            
            # 如果有時間欄位，檢查範圍
            if time_columns.result_rows:
                time_column = time_columns.result_rows[0][0]  # 使用第一個時間欄位
                
                range_sql = f"""
                SELECT min_time, max_time FROM jdbc('mssql_master', '
                    SELECT 
                        MIN({time_column}) as min_time,
                        MAX({time_column}) as max_time
                    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108
                    WHERE {time_column} IS NOT NULL
                ')
                """
                
                result = client.query(range_sql)
                if result.result_rows:
                    min_time, max_time = result.result_rows[0]
                    print(f"\n使用 {time_column} 欄位:")
                    print(f"時間範圍: {min_time} ~ {max_time}")
                    
                    # 計算時間跨度
                    if min_time and max_time:
                        from datetime import datetime
                        min_dt = datetime.fromisoformat(str(min_time).replace('T', ' '))
                        max_dt = datetime.fromisoformat(str(max_time).replace('T', ' '))
                        days_span = (max_dt - min_dt).days
                        print(f"時間跨度: {days_span} 天")
                        
                        # 建議批次大小
                        if days_span > 0:
                            avg_per_day = total_count / days_span
                            print(f"平均每日資料量: {avg_per_day:,.0f} 筆")
                            
                            # 建議批次策略
                            if avg_per_day > 100000:
                                print("💡 建議: 每批次 6-12 小時")
                            elif avg_per_day > 50000:
                                print("💡 建議: 每批次 1 天")
                            else:
                                print("💡 建議: 每批次 2-3 天")
        
        except Exception as e:
            print(f"檢查時間欄位失敗: {e}")
        
        # 檢查年度分布
        print(f"\n📈 年度資料分布:")
        print("-" * 60)
        
        # 嘗試不同的時間欄位名稱
        possible_time_columns = ['CREATE_TIME_', 'LAST_UPDATED_TIME_', 'REV_']
        
        for time_col in possible_time_columns:
            try:
                year_dist_sql = f"""
                SELECT year_data, count_data FROM jdbc('mssql_master', '
                    SELECT 
                        YEAR({time_col}) as year_data,
                        COUNT(*) as count_data
                    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108
                    WHERE {time_col} IS NOT NULL
                    GROUP BY YEAR({time_col})
                    ORDER BY year_data
                ')
                """
                
                year_result = client.query(year_dist_sql)
                if year_result.result_rows:
                    print(f"使用 {time_col} 欄位的年度分布:")
                    for year, count in year_result.result_rows:
                        print(f"  {year}: {count:,} 筆")
                    break
                    
            except Exception as e:
                continue
        else:
            print("無法找到有效的時間欄位進行年度分析")
        
        # 檢查 ClickHouse 目標表狀態
        print(f"\n🎯 ClickHouse 目標表狀態:")
        print("-" * 60)
        
        ch_count = client.command("SELECT count(*) FROM bronze.bpm_act_hi_varinst")
        print(f"bronze.bpm_act_hi_varinst 目前筆數: {ch_count:,}")
        
        if ch_count == 0:
            print("✅ 目標表為空，可以開始同步")
        else:
            print("⚠️ 目標表已有資料，同步前需要清理")
            
    except Exception as e:
        print(f"❌ 檢查失敗: {e}")

if __name__ == "__main__":
    main()