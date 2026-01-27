#!/usr/bin/env python3
"""
修正 ClickHouse 時間精度不一致問題
將 DateTime64(3) 統一改為 DateTime64(6) 以匹配 MSSQL DateTime64(7)
"""

import clickhouse_connect
import sys
from datetime import datetime

def connect_clickhouse():
    """連接到 ClickHouse"""
    try:
        client = clickhouse_connect.get_client(
            host='10.136.218.207',
            port=8121,
            username='default',
            password='default'
        )
        return client
    except Exception as e:
        print(f"❌ 連接 ClickHouse 失敗: {e}")
        return None

def find_datetime_columns(client):
    """找出所有使用 DateTime64(3) 的欄位"""
    print("🔍 掃描所有表格的時間欄位...")
    
    try:
        query = """
        SELECT 
            database,
            table,
            name as column_name,
            type as column_type
        FROM system.columns 
        WHERE database = 'bronze'
          AND type LIKE '%DateTime64(3)%'
        ORDER BY database, table, name
        """
        
        result = client.query(query)
        
        if not result.result_rows:
            print("✅ 沒有找到 DateTime64(3) 欄位")
            return []
            
        print(f"\n📋 找到 {len(result.result_rows)} 個 DateTime64(3) 欄位:")
        print("資料庫".ljust(15) + "表格名稱".ljust(30) + "欄位名稱".ljust(25) + "目前型別")
        print("-" * 90)
        
        columns_to_fix = []
        for row in result.result_rows:
            database, table, column_name, column_type = row
            print(f"{database.ljust(13)} {table.ljust(28)} {column_name.ljust(23)} {column_type}")
            columns_to_fix.append({
                'database': database,
                'table': table,
                'column': column_name,
                'current_type': column_type
            })
        
        return columns_to_fix
        
    except Exception as e:
        print(f"❌ 掃描欄位失敗: {e}")
        return []

def backup_table_structure(client, database, table):
    """備份表格結構"""
    try:
        query = f"SHOW CREATE TABLE {database}.{table}"
        result = client.query(query)
        
        if result.result_rows:
            create_statement = result.result_rows[0][0]
            
            # 儲存到檔案
            backup_file = f"backup_structure_{database}_{table}.sql"
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(f"-- 備份時間: {datetime.now()}\n")
                f.write(f"-- 原始表格: {database}.{table}\n\n")
                f.write(create_statement + ";\n")
            
            print(f"  📁 結構已備份至: {backup_file}")
            return True
            
    except Exception as e:
        print(f"  ❌ 備份失敗: {e}")
        return False

def fix_datetime_precision_for_table(client, table_info):
    """修正單一表格的時間精度"""
    database = table_info['database']
    table = table_info['table']
    column = table_info['column']
    
    print(f"\n🔧 修正表格: {database}.{table}.{column}")
    
    try:
        # 1. 備份表格結構
        print("  📋 備份表格結構...")
        if not backup_table_structure(client, database, table):
            return False
        
        # 2. 修改欄位型別
        print("  🔄 修改欄位型別 DateTime64(3) → DateTime64(6)...")
        alter_query = f"""
        ALTER TABLE {database}.{table} 
        MODIFY COLUMN {column} DateTime64(6)
        """
        
        client.command(alter_query)
        print("  ✅ 欄位型別修改成功")
        
        # 3. 驗證修改結果
        verify_query = f"""
        SELECT type 
        FROM system.columns 
        WHERE database = '{database}' 
          AND table = '{table}' 
          AND name = '{column}'
        """
        
        result = client.query(verify_query)
        if result.result_rows:
            new_type = result.result_rows[0][0]
            if 'DateTime64(6)' in new_type:
                print(f"  ✅ 驗證成功: {new_type}")
                return True
            else:
                print(f"  ❌ 驗證失敗: {new_type}")
                return False
        
        return False
        
    except Exception as e:
        print(f"  ❌ 修正失敗: {e}")
        return False

def main():
    """主函數"""
    print("=" * 70)
    print("🕒 ClickHouse 時間精度修正工具")
    print("=" * 70)
    print(f"⏰ 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎯 目標: DateTime64(3) → DateTime64(6)")
    
    # 連接 ClickHouse
    client = connect_clickhouse()
    if not client:
        sys.exit(1)
    
    # 找出需要修正的欄位
    columns_to_fix = find_datetime_columns(client)
    
    if not columns_to_fix:
        print("\n🎉 所有時間欄位精度已正確！")
        return 0
    
    # 確認是否繼續
    print(f"\n⚠️  將修正 {len(columns_to_fix)} 個欄位")
    print("📋 修正內容:")
    print("  - 將 DateTime64(3) 改為 DateTime64(6)")
    print("  - 自動備份表格結構")
    print("  - 保留所有資料")
    
    # 執行修正
    print(f"\n🚀 開始修正...")
    
    success_count = 0
    failed_tables = []
    
    # 按表格分組處理
    tables_processed = set()
    
    for column_info in columns_to_fix:
        table_key = f"{column_info['database']}.{column_info['table']}"
        
        if table_key not in tables_processed:
            tables_processed.add(table_key)
            
            # 找出這個表格的所有需要修正的欄位
            table_columns = [c for c in columns_to_fix 
                           if c['database'] == column_info['database'] 
                           and c['table'] == column_info['table']]
            
            print(f"\n📊 處理表格: {table_key} ({len(table_columns)} 個欄位)")
            
            table_success = True
            for col_info in table_columns:
                if fix_datetime_precision_for_table(client, col_info):
                    success_count += 1
                else:
                    table_success = False
            
            if not table_success:
                failed_tables.append(table_key)
    
    # 總結報告
    print("\n" + "=" * 70)
    print("📋 修正結果總結:")
    print(f"✅ 成功修正: {success_count} 個欄位")
    
    if failed_tables:
        print(f"❌ 失敗表格: {len(failed_tables)} 個")
        for table in failed_tables:
            print(f"  - {table}")
    
    if success_count == len(columns_to_fix):
        print("\n🎉 所有時間精度修正完成！")
        print("📝 建議:")
        print("  1. 驗證資料完整性")
        print("  2. 測試增量同步功能")
        print("  3. 更新相關文件")
        return 0
    else:
        print(f"\n⚠️  部分修正失敗，請檢查失敗的表格")
        return 1

if __name__ == "__main__":
    sys.exit(main())