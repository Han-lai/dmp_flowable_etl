#!/usr/bin/env python3
"""
修正 ClickHouse 表格的 ORDER BY 設計問題
將不當的 ORDER BY tuple() 改為合適的欄位組合
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

def get_table_columns(client, database, table):
    """取得表格的欄位資訊"""
    try:
        query = f"""
        SELECT 
            name,
            type,
            is_in_primary_key
        FROM system.columns 
        WHERE database = '{database}' 
          AND table = '{table}'
        ORDER BY position
        """
        
        result = client.query(query)
        return result.result_rows
        
    except Exception as e:
        print(f"  ❌ 取得欄位資訊失敗: {e}")
        return []

def analyze_table_for_order_by(client, database, table):
    """分析表格並建議最佳的 ORDER BY 設計"""
    columns = get_table_columns(client, database, table)
    
    if not columns:
        return None
    
    # 尋找合適的 ORDER BY 欄位
    id_columns = []
    time_columns = []
    other_columns = []
    
    for name, col_type, is_primary in columns:
        name_lower = name.lower()
        
        # ID 欄位
        if any(keyword in name_lower for keyword in ['id', 'key', 'inst_id']):
            id_columns.append(name)
        # 時間欄位
        elif any(keyword in name_lower for keyword in ['time', 'date', 'create', 'update', 'start', 'end', 'sync']):
            if 'DateTime' in col_type or 'Date' in col_type:
                time_columns.append(name)
        else:
            other_columns.append(name)
    
    # 建議 ORDER BY 組合
    suggested_order_by = []
    
    # 優先使用主要 ID 欄位
    if id_columns:
        suggested_order_by.append(id_columns[0])
    
    # 加入時間欄位
    if time_columns:
        # 優先選擇建立時間或同步時間
        create_time = next((col for col in time_columns if 'create' in col.lower() or 'start' in col.lower()), None)
        sync_time = next((col for col in time_columns if 'sync' in col.lower()), None)
        
        if create_time:
            suggested_order_by.append(create_time)
        elif sync_time:
            suggested_order_by.append(sync_time)
        elif time_columns:
            suggested_order_by.append(time_columns[0])
    
    # 如果沒有 ID 和時間欄位，使用前兩個欄位
    if not suggested_order_by and other_columns:
        suggested_order_by = other_columns[:2]
    
    return {
        'suggested_columns': suggested_order_by,
        'id_columns': id_columns,
        'time_columns': time_columns,
        'all_columns': [col[0] for col in columns]
    }

# 需要修正的表格和建議的 ORDER BY
TABLES_TO_FIX = {
    'common_flowable_task_stats': {
        'suggested_order_by': ['TaskId', 'TaskCreateTime'],
        'reason': '按任務ID和建立時間排序，提升任務查詢效能'
    },
    'bmp_act_hi_procinst': {
        'suggested_order_by': ['PROC_INST_ID_', 'START_TIME_'],
        'reason': '按流程實例ID和開始時間排序，符合流程查詢模式'
    },
    'bmp_act_hi_taskinst': {
        'suggested_order_by': ['PROC_INST_ID_', 'START_TIME_'],
        'reason': '按流程實例ID和開始時間排序，與流程實例表一致'
    },
    'bmp_act_hi_varinst': {
        'suggested_order_by': ['PROC_INST_ID_', 'CREATE_TIME_'],
        'reason': '按流程實例ID和建立時間排序，提升變數查詢效能'
    },
    'common_hr_employee': {
        'suggested_order_by': ['EmployeeId', 'ModifyDate'],
        'reason': '按員工ID和修改日期排序，提升員工資料查詢效能'
    }
}

def check_columns_exist(client, database, table, columns):
    """檢查指定的欄位是否存在於表格中"""
    existing_columns = get_table_columns(client, database, table)
    existing_names = [col[0] for col in existing_columns]
    
    missing_columns = []
    for col in columns:
        if col not in existing_names:
            missing_columns.append(col)
    
    return missing_columns

def fix_table_order_by(client, database, table, config):
    """修正單一表格的 ORDER BY"""
    print(f"\n🔧 修正表格: {database}.{table}")
    
    try:
        # 1. 檢查欄位是否存在
        missing_columns = check_columns_exist(client, database, table, config['suggested_order_by'])
        
        if missing_columns:
            print(f"  ⚠️  欄位不存在: {', '.join(missing_columns)}")
            
            # 自動分析建議
            analysis = analyze_table_for_order_by(client, database, table)
            if analysis and analysis['suggested_columns']:
                print(f"  💡 自動建議: ORDER BY ({', '.join(analysis['suggested_columns'])})")
                config['suggested_order_by'] = analysis['suggested_columns']
            else:
                print(f"  ❌ 無法找到合適的 ORDER BY 欄位，跳過")
                return False
        
        # 2. 取得目前的 ORDER BY
        current_order_query = f"SHOW CREATE TABLE {database}.{table}"
        result = client.query(current_order_query)
        
        if result.result_rows:
            create_statement = result.result_rows[0][0]
            print(f"  📋 目前設計: {extract_current_order_by(create_statement)}")
        
        # 3. 執行 ALTER TABLE
        order_by_clause = ', '.join(config['suggested_order_by'])
        print(f"  🔄 修改為: ORDER BY ({order_by_clause})")
        print(f"  💭 原因: {config['reason']}")
        
        alter_query = f"""
        ALTER TABLE {database}.{table} 
        MODIFY ORDER BY ({order_by_clause})
        """
        
        client.command(alter_query)
        print(f"  ✅ ORDER BY 修改成功")
        
        # 4. 驗證修改結果
        result = client.query(current_order_query)
        if result.result_rows:
            new_create_statement = result.result_rows[0][0]
            new_order_by = extract_current_order_by(new_create_statement)
            print(f"  ✅ 驗證成功: {new_order_by}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 修正失敗: {e}")
        return False

def extract_current_order_by(create_statement):
    """從 CREATE TABLE 語句中提取目前的 ORDER BY"""
    try:
        order_by_start = create_statement.upper().find('ORDER BY')
        if order_by_start == -1:
            return "無 ORDER BY"
        
        remaining = create_statement[order_by_start + 8:].strip()
        
        # 尋找下一個關鍵字
        keywords = ['PARTITION BY', 'SETTINGS', 'TTL', 'SAMPLE BY']
        end_pos = len(remaining)
        
        for keyword in keywords:
            pos = remaining.upper().find(keyword)
            if pos != -1 and pos < end_pos:
                end_pos = pos
        
        order_by_clause = remaining[:end_pos].strip().rstrip(',)')
        return f"ORDER BY {order_by_clause}"
        
    except Exception as e:
        return f"解析錯誤: {e}"

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

def main():
    """主函數"""
    print("=" * 80)
    print("🔧 ClickHouse ORDER BY 設計修正工具")
    print("=" * 80)
    print(f"⏰ 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎯 目標: 修正不當的 ORDER BY 設計，提升查詢效能")
    
    # 連接 ClickHouse
    client = connect_clickhouse()
    if not client:
        sys.exit(1)
    
    print(f"\n📋 計畫修正 {len(TABLES_TO_FIX)} 個表格:")
    for table, config in TABLES_TO_FIX.items():
        order_by_str = ', '.join(config['suggested_order_by'])
        print(f"  - {table}: ORDER BY ({order_by_str})")
    
    print(f"\n⚠️  修正說明:")
    print("  - ALTER TABLE MODIFY ORDER BY 會觸發背景重新排序")
    print("  - 重新排序期間表格仍可正常查詢")
    print("  - 大表格的重新排序可能需要較長時間")
    print("  - 修正後查詢效能將顯著提升")
    
    print(f"\n🚀 開始修正...")
    
    success_count = 0
    failed_tables = []
    skipped_tables = []
    
    for table_name, config in TABLES_TO_FIX.items():
        # 檢查表格是否存在
        if not check_table_exists(client, 'bronze', table_name):
            print(f"\n⚠️  表格 bronze.{table_name} 不存在，跳過")
            skipped_tables.append(table_name)
            continue
        
        # 修正 ORDER BY
        if fix_table_order_by(client, 'bronze', table_name, config):
            success_count += 1
        else:
            failed_tables.append(table_name)
    
    # 總結報告
    print("\n" + "=" * 80)
    print("📋 修正結果總結:")
    print(f"✅ 成功修正: {success_count} 個表格")
    
    if skipped_tables:
        print(f"⚠️  跳過表格: {len(skipped_tables)} 個")
        for table in skipped_tables:
            print(f"  - {table} (表格不存在)")
    
    if failed_tables:
        print(f"❌ 修正失敗: {len(failed_tables)} 個表格")
        for table in failed_tables:
            print(f"  - {table}")
    
    if success_count > 0:
        print("\n🎉 ORDER BY 設計修正完成！")
        print("📝 效能改善預期:")
        print("  - 查詢速度提升 (利用索引跳過不相關資料)")
        print("  - 範圍查詢效能改善 (按排序欄位查詢)")
        print("  - 壓縮效率提升 (相似資料聚集)")
        
        print(f"\n📊 建議驗證:")
        print("  1. 執行常用查詢測試效能")
        print("  2. 檢查背景 merge 進度")
        print("  3. 監控查詢執行計畫")
        
        return 0
    else:
        print(f"\n⚠️  沒有成功修正任何表格")
        return 1

if __name__ == "__main__":
    sys.exit(main())