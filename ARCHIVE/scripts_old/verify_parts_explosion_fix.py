#!/usr/bin/env python3
"""
驗證 Parts 爆炸問題修正是否成功
檢查 ClickHouse 設定和 Parts 狀態
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

def check_merge_settings(client):
    """檢查 merge_tree 設定是否正確載入"""
    print("🔍 檢查 ClickHouse merge_tree 設定...")
    
    settings_to_check = [
        'parts_to_delay_insert',
        'parts_to_throw_insert', 
        'max_insert_block_size',
        'min_insert_block_size_rows',
        'min_insert_block_size_bytes'
    ]
    
    expected_values = {
        'parts_to_delay_insert': '150',
        'parts_to_throw_insert': '300',
        'max_insert_block_size': '1048576',
        'min_insert_block_size_rows': '262144',
        'min_insert_block_size_bytes': '268435456'
    }
    
    try:
        query = f"""
        SELECT name, value 
        FROM system.settings 
        WHERE name IN ({','.join([f"'{s}'" for s in settings_to_check])})
        ORDER BY name
        """
        
        result = client.query(query)
        settings_dict = {row[0]: row[1] for row in result.result_rows}
        
        print("\n📋 目前設定值:")
        all_correct = True
        
        for setting in settings_to_check:
            current_value = settings_dict.get(setting, 'NOT_FOUND')
            expected_value = expected_values.get(setting, 'UNKNOWN')
            
            if current_value == expected_value:
                status = "✅"
            else:
                status = "❌"
                all_correct = False
                
            print(f"  {status} {setting}: {current_value} (預期: {expected_value})")
        
        return all_correct
        
    except Exception as e:
        print(f"❌ 檢查設定失敗: {e}")
        return False

def check_parts_status(client):
    """檢查各表的 Parts 狀態"""
    print("\n🔍 檢查 Bronze 層表格 Parts 狀態...")
    
    try:
        query = """
        SELECT 
            database,
            table,
            count() as parts_count,
            sum(rows) as total_rows,
            sum(bytes) as total_bytes
        FROM system.parts 
        WHERE active = 1 
          AND database = 'bronze'
        GROUP BY database, table
        ORDER BY parts_count DESC
        """
        
        result = client.query(query)
        
        if not result.result_rows:
            print("⚠️  Bronze 資料庫中沒有找到表格")
            return True
            
        print("\n📊 Parts 狀態報告:")
        print("表格名稱".ljust(30) + "Parts數量".ljust(12) + "總行數".ljust(15) + "總大小(MB)")
        print("-" * 70)
        
        healthy_tables = 0
        total_tables = len(result.result_rows)
        
        for row in result.result_rows:
            database, table, parts_count, total_rows, total_bytes = row
            size_mb = round(total_bytes / 1024 / 1024, 2) if total_bytes else 0
            
            # 判斷 Parts 數量是否健康 (< 10 為健康)
            if parts_count < 10:
                status = "✅"
                healthy_tables += 1
            elif parts_count < 50:
                status = "⚠️ "
            else:
                status = "❌"
                
            print(f"{status} {table.ljust(28)} {str(parts_count).ljust(10)} {str(total_rows).ljust(13)} {size_mb}")
        
        print(f"\n📈 健康度: {healthy_tables}/{total_tables} 表格 Parts 數量正常")
        
        return healthy_tables == total_tables
        
    except Exception as e:
        print(f"❌ 檢查 Parts 狀態失敗: {e}")
        return False

def main():
    """主函數"""
    print("=" * 60)
    print("🔧 Parts 爆炸問題修正驗證")
    print("=" * 60)
    print(f"⏰ 檢查時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 連接 ClickHouse
    client = connect_clickhouse()
    if not client:
        sys.exit(1)
    
    # 檢查設定
    settings_ok = check_merge_settings(client)
    
    # 檢查 Parts 狀態
    parts_ok = check_parts_status(client)
    
    # 總結
    print("\n" + "=" * 60)
    print("📋 驗證結果總結:")
    
    if settings_ok:
        print("✅ ClickHouse merge_tree 設定已正確載入")
    else:
        print("❌ ClickHouse merge_tree 設定載入失敗")
    
    if parts_ok:
        print("✅ 所有表格 Parts 數量正常")
    else:
        print("⚠️  部分表格 Parts 數量偏高，建議觀察")
    
    if settings_ok and parts_ok:
        print("\n🎉 Parts 爆炸問題修正成功！")
        return 0
    elif settings_ok:
        print("\n⚠️  設定已載入，Parts 狀態需要時間改善")
        return 0
    else:
        print("\n❌ 修正未完全成功，請檢查設定")
        return 1

if __name__ == "__main__":
    sys.exit(main())