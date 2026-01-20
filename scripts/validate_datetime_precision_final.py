#!/usr/bin/env python3
"""
最終驗證所有時間欄位精度是否已標準化
檢查所有 Bronze 層表格的時間欄位精度狀況
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

def check_all_datetime_columns(client):
    """檢查所有時間欄位的精度"""
    print("🔍 掃描所有 Bronze 層時間欄位...")
    
    try:
        # 查詢所有時間相關欄位
        query = """
        SELECT 
            database,
            table,
            name as column_name,
            type as column_type
        FROM system.columns 
        WHERE database = 'bronze'
          AND (type LIKE '%DateTime%' OR type LIKE '%Date%')
        ORDER BY table, name
        """
        
        result = client.query(query)
        
        if not result.result_rows:
            print("⚠️  沒有找到時間欄位")
            return True, {}
            
        # 分類統計
        datetime64_3_count = 0
        datetime64_6_count = 0
        other_datetime_count = 0
        date_count = 0
        
        columns_by_precision = {
            'DateTime64(3)': [],
            'DateTime64(6)': [],
            'Other DateTime': [],
            'Date': []
        }
        
        print(f"\n📊 找到 {len(result.result_rows)} 個時間欄位:")
        print("表格名稱".ljust(35) + "欄位名稱".ljust(25) + "型別")
        print("-" * 80)
        
        for row in result.result_rows:
            database, table, column_name, column_type = row
            print(f"{table.ljust(33)} {column_name.ljust(23)} {column_type}")
            
            # 分類統計
            if 'DateTime64(3)' in column_type:
                datetime64_3_count += 1
                columns_by_precision['DateTime64(3)'].append(f"{table}.{column_name}")
            elif 'DateTime64(6)' in column_type:
                datetime64_6_count += 1
                columns_by_precision['DateTime64(6)'].append(f"{table}.{column_name}")
            elif 'DateTime' in column_type:
                other_datetime_count += 1
                columns_by_precision['Other DateTime'].append(f"{table}.{column_name}")
            elif 'Date' in column_type:
                date_count += 1
                columns_by_precision['Date'].append(f"{table}.{column_name}")
        
        # 統計報告
        print(f"\n📈 精度統計:")
        print(f"  ✅ DateTime64(6): {datetime64_6_count} 個欄位")
        print(f"  ❌ DateTime64(3): {datetime64_3_count} 個欄位")
        print(f"  ℹ️  其他 DateTime: {other_datetime_count} 個欄位")
        print(f"  📅 Date 型別: {date_count} 個欄位")
        
        # 詳細列表
        if datetime64_3_count > 0:
            print(f"\n❌ 仍需修正的 DateTime64(3) 欄位:")
            for column in columns_by_precision['DateTime64(3)']:
                print(f"  - {column}")
        
        if datetime64_6_count > 0:
            print(f"\n✅ 已標準化的 DateTime64(6) 欄位:")
            for column in columns_by_precision['DateTime64(6)'][:10]:  # 只顯示前10個
                print(f"  - {column}")
            if len(columns_by_precision['DateTime64(6)']) > 10:
                print(f"  ... 還有 {len(columns_by_precision['DateTime64(6)']) - 10} 個")
        
        # 判斷是否完全標準化
        is_standardized = datetime64_3_count == 0
        
        return is_standardized, columns_by_precision
        
    except Exception as e:
        print(f"❌ 檢查失敗: {e}")
        return False, {}

def check_sync_performance(client):
    """檢查同步效能相關指標"""
    print("\n🔍 檢查同步效能指標...")
    
    try:
        # 檢查最近同步時間
        query = """
        SELECT 
            table_name,
            max(_sync_time) as last_sync,
            count() as row_count
        FROM (
            SELECT 'bpm_act_hi_procinst' as table_name, _sync_time FROM bronze.bpm_act_hi_procinst
            UNION ALL
            SELECT 'bpm_act_hi_taskinst' as table_name, _sync_time FROM bronze.bpm_act_hi_taskinst
            UNION ALL
            SELECT 'bpm_act_hi_varinst' as table_name, _sync_time FROM bronze.bpm_act_hi_varinst
            UNION ALL
            SELECT 'common_hr_employee' as table_name, _sync_time FROM bronze.common_hr_employee
        )
        GROUP BY table_name
        ORDER BY last_sync DESC
        """
        
        result = client.query(query)
        
        if result.result_rows:
            print("📊 同步狀態:")
            print("表格名稱".ljust(30) + "最後同步時間".ljust(25) + "資料筆數")
            print("-" * 70)
            
            for row in result.result_rows:
                table_name, last_sync, row_count = row
                sync_time_str = last_sync.strftime('%Y-%m-%d %H:%M:%S') if last_sync else 'N/A'
                print(f"{table_name.ljust(28)} {sync_time_str.ljust(23)} {row_count:,}")
        
        return True
        
    except Exception as e:
        print(f"⚠️  同步狀態檢查失敗: {e}")
        return False

def main():
    """主函數"""
    print("=" * 80)
    print("🎯 時間精度標準化最終驗證")
    print("=" * 80)
    print(f"⏰ 驗證時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📋 檢查項目:")
    print("  1. 所有時間欄位精度統計")
    print("  2. DateTime64(3) 剩餘欄位")
    print("  3. DateTime64(6) 標準化欄位")
    print("  4. 同步效能指標")
    
    # 連接 ClickHouse
    client = connect_clickhouse()
    if not client:
        sys.exit(1)
    
    # 檢查時間欄位精度
    is_standardized, precision_stats = check_all_datetime_columns(client)
    
    # 檢查同步效能
    sync_ok = check_sync_performance(client)
    
    # 總結報告
    print("\n" + "=" * 80)
    print("📋 標準化驗證結果:")
    
    if is_standardized:
        print("🎉 時間精度標準化完成！")
        print("✅ 所有時間欄位已使用 DateTime64(6) 或適當型別")
    else:
        remaining_count = len(precision_stats.get('DateTime64(3)', []))
        print(f"⚠️  標準化進行中，還有 {remaining_count} 個 DateTime64(3) 欄位需要修正")
    
    standardized_count = len(precision_stats.get('DateTime64(6)', []))
    print(f"📊 已標準化欄位: {standardized_count} 個")
    
    if sync_ok:
        print("✅ 同步功能正常")
    else:
        print("⚠️  同步狀態需要檢查")
    
    # 建議後續步驟
    if is_standardized:
        print("\n📝 建議後續步驟:")
        print("  1. 更新 DDL 模板使用 DateTime64(6)")
        print("  2. 更新同步腳本的時間格式處理")
        print("  3. 測試端到端資料流")
        print("  4. 更新開發文件和規範")
        return 0
    else:
        print("\n📝 需要完成的工作:")
        print("  1. 修正剩餘的 DateTime64(3) 欄位")
        print("  2. 處理 NULL 值轉換問題")
        print("  3. 重新執行標準化腳本")
        return 1

if __name__ == "__main__":
    sys.exit(main())