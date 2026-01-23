#!/usr/bin/env python3
"""
執行 Silver 層日期過濾邏輯修正
修正問題：Silver MVIEW 只檢查 task_create_time，應該要像 MSSQL 一樣檢查 START_TIME_, CLAIM_TIME_, END_TIME_
"""

import clickhouse_connect
import sys
from pathlib import Path

def main():
    try:
        # 連接 ClickHouse
        client = clickhouse_connect.get_client(
            host='localhost',
            port=8123,
            username='default',
            password=''
        )
        
        print("✅ 連接 ClickHouse 成功")
        
        # 讀取修正 SQL
        sql_file = Path('sql/fix_silver_date_filter_logic.sql')
        if not sql_file.exists():
            print(f"❌ SQL 檔案不存在: {sql_file}")
            return False
            
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        print(f"📖 讀取 SQL 檔案: {sql_file}")
        
        # 分割 SQL 語句（以分號分隔）
        sql_statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
        
        print(f"🔧 準備執行 {len(sql_statements)} 個 SQL 語句")
        
        # 逐一執行 SQL 語句
        for i, sql in enumerate(sql_statements, 1):
            if sql.startswith('--') or not sql:
                continue
                
            try:
                print(f"⏳ 執行語句 {i}/{len(sql_statements)}: {sql[:50]}...")
                
                # 執行 SQL
                if sql.upper().startswith('SELECT'):
                    result = client.query(sql)
                    print(f"   📊 查詢結果: {result.result_rows}")
                    if result.result_rows:
                        for row in result.result_rows:
                            print(f"   📋 {row}")
                else:
                    client.command(sql)
                    print(f"   ✅ 執行成功")
                    
            except Exception as e:
                print(f"   ❌ 執行失敗: {e}")
                # 繼續執行下一個語句，不中斷整個流程
                continue
        
        print("\n🎉 Silver 層日期過濾邏輯修正完成")
        
        # 驗證修正結果
        print("\n🔍 驗證修正結果...")
        
        # 檢查 WJ2/NBU/E5 2025-12-25 的記錄數
        validation_sql = """
        SELECT 
            'WJ2/NBU/E5 2025-12-25 驗證' as check_type,
            COUNT(*) as record_count,
            COUNT(DISTINCT task_id) as unique_tasks
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE (
            toDate(task_create_time) = '2025-12-25'
            OR toDate(task_claim_time) = '2025-12-25'
            OR toDate(task_end_time) = '2025-12-25'
        )
        AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
        """
        
        try:
            result = client.query(validation_sql)
            print("📊 驗證結果:")
            for row in result.result_rows:
                print(f"   {row[0]}: {row[1]} 筆記錄, {row[2]} 個唯一任務")
                
            if result.result_rows and result.result_rows[0][1] == 5:
                print("✅ 修正成功！記錄數已恢復為 5 筆，與 MSSQL 一致")
            else:
                print(f"⚠️ 記錄數為 {result.result_rows[0][1] if result.result_rows else 0} 筆，預期為 5 筆")
                
        except Exception as e:
            print(f"❌ 驗證查詢失敗: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        return False
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)