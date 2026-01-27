#!/usr/bin/env python3
"""
批次重建表格以實現時間精度標準化
將失敗的表格重建為 DateTime64(6) 標準精度
"""

import clickhouse_connect
import sys
from datetime import datetime
import time

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

# 需要重建的表格和欄位對照表
TABLES_TO_REBUILD = {
    'bmp_act_hi_procinst': {
        'datetime_columns': ['END_TIME_', 'START_TIME_', '_sync_time'],
        'nullable_columns': ['END_TIME_'],  # 可以為 NULL 的欄位
        'order_by': 'START_TIME_',
        'partition_by': '_sync_time'
    },
    'bmp_act_hi_taskinst': {
        'datetime_columns': ['CLAIM_TIME_', 'DUE_DATE_', 'END_TIME_', 'START_TIME_', '_sync_time'],
        'nullable_columns': ['CLAIM_TIME_', 'DUE_DATE_', 'END_TIME_'],
        'order_by': 'START_TIME_',
        'partition_by': '_sync_time'
    },
    'bmp_act_hi_varinst': {
        'datetime_columns': ['CREATE_TIME_', '_sync_time'],
        'nullable_columns': ['CREATE_TIME_'],
        'order_by': 'CREATE_TIME_',
        'partition_by': '_sync_time'
    },
    'common_hr_employee': {
        'datetime_columns': ['ModifyDate', 'TerminateDate'],
        'nullable_columns': ['ModifyDate', 'TerminateDate'],
        'order_by': 'ModifyDate',
        'partition_by': 'ModifyDate'
    },
    'common_process_role_group': {
        'datetime_columns': ['CreateDatetime', 'UpdateDatetime'],
        'nullable_columns': ['CreateDatetime'],
        'order_by': 'UpdateDatetime',
        'partition_by': 'UpdateDatetime'
    },
    'common_process_role_group_mapping': {
        'datetime_columns': ['CreateDatetime', 'UpdateDatetime'],
        'nullable_columns': ['CreateDatetime', 'UpdateDatetime'],
        'order_by': 'UpdateDatetime',
        'partition_by': 'UpdateDatetime'
    }
}

def get_table_structure(client, database, table):
    """取得表格結構"""
    try:
        query = f"SHOW CREATE TABLE {database}.{table}"
        result = client.query(query)
        
        if result.result_rows:
            return result.result_rows[0][0]
        return None
        
    except Exception as e:
        print(f"  ❌ 取得表格結構失敗: {e}")
        return None

def backup_table_data(client, database, table):
    """備份表格資料統計"""
    try:
        query = f"""
        SELECT 
            count() as row_count,
            sum(bytes) as total_bytes
        FROM system.parts 
        WHERE database = '{database}' 
          AND table = '{table}' 
          AND active = 1
        """
        
        result = client.query(query)
        if result.result_rows:
            row_count, total_bytes = result.result_rows[0]
            print(f"  📊 原表格統計: {row_count:,} 行, {total_bytes/1024/1024:.2f} MB")
            return row_count, total_bytes
        
        return 0, 0
        
    except Exception as e:
        print(f"  ⚠️  無法取得表格統計: {e}")
        return 0, 0

def create_new_table_ddl(original_ddl, table_config):
    """根據原始 DDL 建立新表格的 DDL，並修正時間精度"""
    
    # 替換表格名稱
    new_ddl = original_ddl.replace(
        f"CREATE TABLE bronze.{table_config['table_name']}",
        f"CREATE TABLE bronze.{table_config['table_name']}_new"
    )
    
    # 替換時間欄位精度
    for column in table_config['datetime_columns']:
        if column in table_config['nullable_columns']:
            # Nullable 欄位
            new_ddl = new_ddl.replace(
                f"`{column}` Nullable(DateTime64(3))",
                f"`{column}` Nullable(DateTime64(6))"
            )
        else:
            # 非 Nullable 欄位
            new_ddl = new_ddl.replace(
                f"`{column}` DateTime64(3)",
                f"`{column}` DateTime64(6)"
            )
    
    return new_ddl

def rebuild_single_table(client, database, table_name, table_config):
    """重建單一表格"""
    print(f"\n🔧 重建表格: {database}.{table_name}")
    
    try:
        # 1. 備份原表格統計
        print("  📋 備份原表格資訊...")
        original_count, original_bytes = backup_table_data(client, database, table_name)
        
        # 2. 取得原表格結構
        print("  📖 取得原表格結構...")
        original_ddl = get_table_structure(client, database, table_name)
        if not original_ddl:
            print("  ❌ 無法取得原表格結構")
            return False
        
        # 備份 DDL 到檔案
        backup_file = f"backup_ddl_{database}_{table_name}.sql"
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(f"-- 重建前備份: {datetime.now()}\n")
            f.write(f"-- 原表格: {database}.{table_name}\n\n")
            f.write(original_ddl + ";\n")
        print(f"  📁 DDL 已備份至: {backup_file}")
        
        # 3. 建立新表格
        print("  🏗️  建立新表格...")
        table_config['table_name'] = table_name
        new_ddl = create_new_table_ddl(original_ddl, table_config)
        
        client.command(new_ddl)
        print("  ✅ 新表格建立成功")
        
        # 4. 複製資料
        print("  📦 複製資料...")
        copy_query = f"""
        INSERT INTO {database}.{table_name}_new 
        SELECT * FROM {database}.{table_name}
        """
        
        client.command(copy_query)
        print("  ✅ 資料複製完成")
        
        # 5. 驗證資料完整性
        print("  🔍 驗證資料完整性...")
        verify_query = f"""
        SELECT count() as new_count 
        FROM {database}.{table_name}_new
        """
        
        result = client.query(verify_query)
        if result.result_rows:
            new_count = result.result_rows[0][0]
            if new_count == original_count:
                print(f"  ✅ 資料驗證成功: {new_count:,} 行")
            else:
                print(f"  ❌ 資料驗證失敗: 原始 {original_count:,} 行 vs 新表格 {new_count:,} 行")
                return False
        
        # 6. 原子性替換表格
        print("  🔄 執行原子性表格替換...")
        rename_query = f"""
        RENAME TABLE 
            {database}.{table_name} TO {database}.{table_name}_old,
            {database}.{table_name}_new TO {database}.{table_name}
        """
        
        client.command(rename_query)
        print("  ✅ 表格替換成功")
        
        # 7. 清理舊表格 (可選，先保留以防萬一)
        print("  🗑️  保留舊表格 (_old) 以防萬一")
        
        # 8. 驗證新表格的時間精度
        print("  🔍 驗證時間精度...")
        for column in table_config['datetime_columns']:
            verify_precision_query = f"""
            SELECT type 
            FROM system.columns 
            WHERE database = '{database}' 
              AND table = '{table_name}' 
              AND name = '{column}'
            """
            
            result = client.query(verify_precision_query)
            if result.result_rows:
                column_type = result.result_rows[0][0]
                if 'DateTime64(6)' in column_type:
                    print(f"    ✅ {column}: {column_type}")
                else:
                    print(f"    ❌ {column}: {column_type} (應為 DateTime64(6))")
        
        print(f"  🎉 表格 {table_name} 重建完成！")
        return True
        
    except Exception as e:
        print(f"  ❌ 重建失敗: {e}")
        
        # 嘗試清理失敗的新表格
        try:
            client.command(f"DROP TABLE IF EXISTS {database}.{table_name}_new")
            print("  🧹 已清理失敗的新表格")
        except:
            pass
            
        return False

def main():
    """主函數"""
    print("=" * 80)
    print("🔧 批次表格重建工具 - 時間精度標準化")
    print("=" * 80)
    print(f"⏰ 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 目標: 將失敗表格重建為 DateTime64(6) 標準精度")
    
    # 連接 ClickHouse
    client = connect_clickhouse()
    if not client:
        sys.exit(1)
    
    print(f"\n📋 計畫重建 {len(TABLES_TO_REBUILD)} 個表格:")
    for table_name, config in TABLES_TO_REBUILD.items():
        columns_str = ', '.join(config['datetime_columns'])
        print(f"  - {table_name}: {columns_str}")
    
    # 確認是否繼續
    print(f"\n⚠️  重建過程說明:")
    print("  1. 建立新表格 (使用 DateTime64(6) 精度)")
    print("  2. 複製所有資料到新表格")
    print("  3. 驗證資料完整性")
    print("  4. 原子性替換表格")
    print("  5. 保留舊表格 (_old) 作為備份")
    
    # 開始重建
    print(f"\n🚀 開始批次重建...")
    
    success_count = 0
    failed_tables = []
    
    for table_name, table_config in TABLES_TO_REBUILD.items():
        if rebuild_single_table(client, 'bronze', table_name, table_config):
            success_count += 1
        else:
            failed_tables.append(table_name)
        
        # 每個表格之間稍作停頓
        if table_name != list(TABLES_TO_REBUILD.keys())[-1]:
            print("\n  ⏳ 等待 3 秒後繼續...")
            time.sleep(3)
    
    # 總結報告
    print("\n" + "=" * 80)
    print("📋 重建結果總結:")
    print(f"✅ 成功重建: {success_count} 個表格")
    
    if failed_tables:
        print(f"❌ 重建失敗: {len(failed_tables)} 個表格")
        for table in failed_tables:
            print(f"  - {table}")
    
    if success_count == len(TABLES_TO_REBUILD):
        print("\n🎉 所有表格重建完成！")
        print("📝 後續步驟:")
        print("  1. 驗證業務功能正常")
        print("  2. 測試增量同步")
        print("  3. 確認無問題後清理 _old 表格")
        return 0
    else:
        print(f"\n⚠️  部分表格重建失敗，請檢查失敗原因")
        return 1

if __name__ == "__main__":
    sys.exit(main())