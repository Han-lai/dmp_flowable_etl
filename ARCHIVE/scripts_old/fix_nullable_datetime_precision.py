#!/usr/bin/env python3
"""
修正 Nullable DateTime 欄位的精度問題
針對包含 NULL 值的欄位，使用 Nullable(DateTime64(6)) 型別
"""

import clickhouse_connect
import sys
from datetime import datetime

def connect_clickhouse():
    """連接到 ClickHouse"""
    try:
        client = clickhouse_connect.get_client(
            host='REDACTED_IP',
            port=8121,
            username='default',
            password='default'
        )
        return client
    except Exception as e:
        print(f"❌ 連接 ClickHouse 失敗: {e}")
        return None

# 需要修正的 Nullable 欄位
NULLABLE_COLUMNS_TO_FIX = {
    'bpm_act_hi_procinst': ['END_TIME_'],
    'bpm_act_hi_taskinst': ['CLAIM_TIME_', 'DUE_DATE_', 'END_TIME_'],
    'bpm_act_hi_varinst': ['CREATE_TIME_'],
    'common_hr_employee': ['TerminateDate'],
    'common_process_role_group': ['CreateDatetime'],
    'common_process_role_group_mapping': ['CreateDatetime', 'UpdateDatetime']
}

def check_table_exists(client, database, table):
    """檢查表格是否存在"""
    try:
        query = f"""
        SELECT count() 
        FROM system.tables 
        WHERE database = '{database}' 
          AND name = '{table}'
        """
        result = client.query(query)
        return result.result_rows[0][0] > 0
    except:
        return False

def get_column_info(client, database, table, column):
    """取得欄位資訊"""
    try:
        query = f"""
        SELECT type, is_in_primary_key
        FROM system.columns 
        WHERE database = '{database}' 
          AND table = '{table}' 
          AND name = '{column}'
        """
        result = client.query(query)
        if result.result_rows:
            return result.result_rows[0]
        return None, None
    except Exception as e:
        print(f"  ❌ 取得欄位資訊失敗: {e}")
        return None, None

def fix_nullable_column(client, database, table, column):
    """修正單一 Nullable 欄位的精度"""
    print(f"\n🔧 修正欄位: {database}.{table}.{column}")
    
    try:
        # 1. 檢查欄位目前型別
        current_type, is_primary = get_column_info(client, database, table, column)
        if not current_type:
            print(f"  ❌ 欄位不存在")
            return False
            
        print(f"  📋 目前型別: {current_type}")
        
        # 2. 檢查是否已經是正確型別
        if 'Nullable(DateTime64(6))' in current_type:
            print(f"  ✅ 欄位已是正確型別")
            return True
            
        # 3. 檢查是否包含 DateTime64(3)
        if 'DateTime64(3)' not in current_type:
            print(f"  ⚠️  欄位不是 DateTime64(3) 型別，跳過")
            return True
            
        # 4. 修改欄位型別為 Nullable(DateTime64(6))
        print(f"  🔄 修改型別: {current_type} → Nullable(DateTime64(6))")
        
        alter_query = f"""
        ALTER TABLE {database}.{table} 
        MODIFY COLUMN {column} Nullable(DateTime64(6))
        """
        
        client.command(alter_query)
        print(f"  ✅ 欄位型別修改成功")
        
        # 5. 驗證修改結果
        new_type, _ = get_column_info(client, database, table, column)
        if new_type and 'Nullable(DateTime64(6))' in new_type:
            print(f"  ✅ 驗證成功: {new_type}")
            return True
        else:
            print(f"  ❌ 驗證失敗: {new_type}")
            return False
            
    except Exception as e:
        print(f"  ❌ 修正失敗: {e}")
        return False

def main():
    """主函數"""
    print("=" * 70)
    print("🔧 Nullable DateTime 欄位精度修正工具")
    print("=" * 70)
    print(f"⏰ 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎯 目標: Nullable(DateTime64(3)) → Nullable(DateTime64(6))")
    
    # 連接 ClickHouse
    client = connect_clickhouse()
    if not client:
        sys.exit(1)
    
    # 統計需要修正的欄位
    total_columns = sum(len(columns) for columns in NULLABLE_COLUMNS_TO_FIX.values())
    print(f"\n📋 計畫修正 {len(NULLABLE_COLUMNS_TO_FIX)} 個表格的 {total_columns} 個欄位:")
    
    for table, columns in NULLABLE_COLUMNS_TO_FIX.items():
        print(f"  - {table}: {', '.join(columns)}")
    
    print(f"\n🚀 開始修正...")
    
    success_count = 0
    failed_columns = []
    skipped_tables = []
    
    for table_name, columns in NULLABLE_COLUMNS_TO_FIX.items():
        print(f"\n📊 處理表格: bronze.{table_name}")
        
        # 檢查表格是否存在
        if not check_table_exists(client, 'bronze', table_name):
            print(f"  ⚠️  表格不存在，跳過")
            skipped_tables.append(table_name)
            continue
        
        # 處理每個欄位
        for column in columns:
            if fix_nullable_column(client, 'bronze', table_name, column):
                success_count += 1
            else:
                failed_columns.append(f"{table_name}.{column}")
    
    # 總結報告
    print("\n" + "=" * 70)
    print("📋 修正結果總結:")
    print(f"✅ 成功修正: {success_count} 個欄位")
    
    if skipped_tables:
        print(f"⚠️  跳過表格: {len(skipped_tables)} 個")
        for table in skipped_tables:
            print(f"  - {table} (表格不存在)")
    
    if failed_columns:
        print(f"❌ 修正失敗: {len(failed_columns)} 個欄位")
        for column in failed_columns:
            print(f"  - {column}")
    
    if success_count > 0:
        print("\n🎉 Nullable 欄位精度修正完成！")
        print("📝 建議:")
        print("  1. 驗證修正後的欄位功能正常")
        print("  2. 測試包含 NULL 值的資料查詢")
        print("  3. 檢查增量同步是否正常")
        
        # 執行驗證
        print(f"\n🔍 執行驗證...")
        verify_query = """
        SELECT 
            database,
            table,
            name as column_name,
            type as column_type
        FROM system.columns 
        WHERE database = 'bronze'
          AND type LIKE '%DateTime64(6)%'
          AND table IN ('bpm_act_hi_procinst', 'bmp_act_hi_taskinst', 'bmp_act_hi_varinst', 
                       'common_hr_employee', 'common_process_role_group', 'common_process_role_group_mapping')
        ORDER BY table, name
        """
        
        try:
            result = client.query(verify_query)
            if result.result_rows:
                print(f"\n📊 修正後的 DateTime64(6) 欄位:")
                print("表格名稱".ljust(35) + "欄位名稱".ljust(20) + "型別")
                print("-" * 75)
                for row in result.result_rows:
                    database, table, column, col_type = row
                    print(f"{table.ljust(33)} {column.ljust(18)} {col_type}")
            else:
                print("  ⚠️  沒有找到 DateTime64(6) 欄位")
        except Exception as e:
            print(f"  ❌ 驗證查詢失敗: {e}")
        
        return 0
    else:
        print(f"\n⚠️  沒有成功修正任何欄位")
        return 1

if __name__ == "__main__":
    sys.exit(main())