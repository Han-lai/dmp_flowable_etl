#!/usr/bin/env python3
"""
檢查 MSSQL 到 ClickHouse 時間欄位 NULL 值處理問題
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clickhouse_connect

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    try:
        client = clickhouse_connect.get_client(
            host='10.136.218.207',
            port=8121,
            username='default',
            password='default'
        )
        return client
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        return None

def check_taskinst_table_structure(client):
    """檢查 taskinst 表結構和 NULL 值問題"""
    print("🔍 檢查 bronze.bpm_act_hi_taskinst 表結構...")
    print("="*60)
    
    try:
        # 檢查表結構
        structure = client.query("DESCRIBE bronze.bpm_act_hi_taskinst")
        print("表結構:")
        for row in structure.result_rows:
            column_name, column_type, default_type, default_expr, comment, codec_expr, ttl_expr = row
            nullable = "Nullable" in column_type
            print(f"   {column_name}: {column_type} {'(可NULL)' if nullable else '(不可NULL)'}")
        
        # 檢查時間欄位的 NULL 值情況
        print("\n時間欄位 NULL 值統計:")
        
        time_columns = ['START_TIME_', 'END_TIME_', 'CLAIM_TIME_']
        
        for col in time_columns:
            try:
                null_check = client.query(f"""
                SELECT 
                    COUNT(*) as total_records,
                    COUNT({col}) as non_null_records,
                    COUNT(*) - COUNT({col}) as null_records,
                    round((COUNT(*) - COUNT({col})) * 100.0 / COUNT(*), 2) as null_percentage
                FROM bronze.bpm_act_hi_taskinst
                """)
                
                if null_check.result_rows:
                    total, non_null, null_count, null_pct = null_check.result_rows[0]
                    print(f"   {col}:")
                    print(f"     總記錄: {total:,}")
                    print(f"     非 NULL: {non_null:,}")
                    print(f"     NULL 值: {null_count:,} ({null_pct}%)")
                
            except Exception as e:
                print(f"   ❌ {col}: 查詢失敗 - {e}")
        
        # 檢查範例資料（避免直接查詢可能有問題的欄位）
        print("\n範例資料（避開時間欄位）:")
        try:
            sample = client.query("""
            SELECT ID_, TASK_DEF_KEY_, NAME_, ASSIGNEE_
            FROM bronze.bpm_act_hi_taskinst 
            LIMIT 5
            """)
            
            for i, row in enumerate(sample.result_rows, 1):
                task_id, task_def_key, name, assignee = row
                print(f"   {i}. ID: {task_id}, DEF_KEY: {task_def_key}, NAME: {name}, ASSIGNEE: {assignee}")
                
        except Exception as e:
            print(f"   ❌ 範例資料查詢失敗: {e}")
        
    except Exception as e:
        print(f"❌ 表結構檢查失敗: {e}")

def check_datetime_conversion_methods(client):
    """測試不同的時間轉換方法"""
    print("\n🔍 測試時間欄位轉換方法...")
    print("="*60)
    
    conversion_methods = [
        ("直接查詢", "START_TIME_"),
        ("toDateTimeOrNull", "toDateTimeOrNull(START_TIME_)"),
        ("COALESCE + toDateTime", "COALESCE(toDateTimeOrNull(START_TIME_), toDateTime('1970-01-01 00:00:00'))"),
        ("COALESCE + toDate", "COALESCE(toDate(START_TIME_), toDate('1970-01-01'))"),
        ("條件判斷", "CASE WHEN START_TIME_ IS NOT NULL THEN START_TIME_ ELSE toDateTime('1970-01-01 00:00:00') END")
    ]
    
    for method_name, sql_expr in conversion_methods:
        try:
            print(f"\n測試方法: {method_name}")
            test_query = f"""
            SELECT {sql_expr} as converted_time
            FROM bronze.bpm_act_hi_taskinst 
            LIMIT 3
            """
            
            result = client.query(test_query)
            print(f"   ✅ 成功 - 返回 {len(result.result_rows)} 筆資料")
            
            for i, row in enumerate(result.result_rows, 1):
                print(f"   {i}. {row[0]}")
                
        except Exception as e:
            print(f"   ❌ 失敗 - {e}")

def check_sync_process_datetime_handling(client):
    """檢查同步過程中的時間處理"""
    print("\n🔍 檢查同步過程時間處理...")
    print("="*60)
    
    try:
        # 檢查是否有同步相關的表或日誌
        sync_tables = client.query("""
        SELECT name, engine, total_rows 
        FROM system.tables 
        WHERE database = 'bronze' 
          AND (name LIKE '%sync%' OR name LIKE '%etl%' OR name LIKE '%load%')
        ORDER BY name
        """)
        
        if sync_tables.result_rows:
            print("同步相關表:")
            for row in sync_tables.result_rows:
                name, engine, rows = row
                print(f"   {name}: {engine}, {rows:,} 筆")
        else:
            print("未找到同步相關表")
        
        # 檢查表的建立時間和最後修改時間
        table_info = client.query("""
        SELECT 
            name,
            engine,
            create_table_query
        FROM system.tables 
        WHERE database = 'bronze' AND name = 'bpm_act_hi_taskinst'
        """)
        
        if table_info.result_rows:
            name, engine, create_query = table_info.result_rows[0]
            print(f"\n表資訊:")
            print(f"   表名: {name}")
            print(f"   引擎: {engine}")
            print(f"   建立語句: {create_query[:200]}...")
        
    except Exception as e:
        print(f"❌ 同步過程檢查失敗: {e}")

def suggest_fix_solutions(client):
    """建議修正方案"""
    print("\n💡 建議修正方案...")
    print("="*60)
    
    print("1. 立即解決方案 - 使用 NULL 安全的查詢:")
    print("   - 使用 toDateTimeOrNull() 函數")
    print("   - 使用 COALESCE() 提供預設值")
    print("   - 使用條件判斷避免 NULL 值")
    
    print("\n2. 根本解決方案 - 修正表結構:")
    print("   - 將時間欄位改為 Nullable 類型")
    print("   - 或在同步時處理 NULL 值")
    
    print("\n3. 測試修正後的查詢:")
    
    # 測試修正後的查詢
    try:
        fixed_query = """
        SELECT 
            ID_,
            TASK_DEF_KEY_,
            COALESCE(toDateTimeOrNull(START_TIME_), toDateTime('1970-01-01 00:00:00')) as start_time_safe,
            toDateTimeOrNull(END_TIME_) as end_time_safe,
            toDateTimeOrNull(CLAIM_TIME_) as claim_time_safe
        FROM bronze.bpm_act_hi_taskinst 
        LIMIT 5
        """
        
        result = client.query(fixed_query)
        print("   ✅ 修正後查詢成功")
        print(f"   返回 {len(result.result_rows)} 筆資料")
        
        for i, row in enumerate(result.result_rows, 1):
            task_id, task_def, start_time, end_time, claim_time = row
            print(f"   {i}. ID: {task_id}, 開始: {start_time}, 結束: {end_time}, 認領: {claim_time}")
        
    except Exception as e:
        print(f"   ❌ 修正後查詢仍失敗: {e}")

def main():
    """主執行函數"""
    try:
        # 建立連線
        client = get_clickhouse_client()
        if client is None:
            return False
        
        # 執行各項檢查
        check_taskinst_table_structure(client)
        check_datetime_conversion_methods(client)
        check_sync_process_datetime_handling(client)
        suggest_fix_solutions(client)
        
        print("\n✅ 時間欄位 NULL 值問題檢查完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 執行過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            client.close()
        except:
            pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)