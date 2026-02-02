#!/usr/bin/env python3
"""
檢查所有 BPM 表的 MSSQL vs ClickHouse 資料量比較
"""

import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("🔍 檢查所有 BPM 表資料量比較")
    print("=" * 80)
    
    # 定義要檢查的表格對應關係
    tables_to_check = [
        {
            'name': 'ACT_HI_IDENTITYLINK_0108',
            'mssql_table': 'APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0108',
            'clickhouse_table': 'bronze.bpm_act_hi_identitylink'
        },
        {
            'name': 'ACT_HI_PROCINST_0108',
            'mssql_table': 'APP_SRV_BPM.dbo.ACT_HI_PROCINST_0108',
            'clickhouse_table': 'bronze.bpm_act_hi_procinst'
        },
        {
            'name': 'ACT_HI_TASKINST_0108',
            'mssql_table': 'APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108',
            'clickhouse_table': 'bronze.bpm_act_hi_taskinst'
        },
        {
            'name': 'ACT_HI_VARINST_0108',
            'mssql_table': 'APP_SRV_BPM.dbo.ACT_HI_VARINST_0108',
            'clickhouse_table': 'bronze.bpm_act_hi_varinst'
        },
        {
            'name': 'ACT_RE_PROCDEF_0108',
            'mssql_table': 'APP_SRV_BPM.dbo.ACT_RE_PROCDEF_0108',
            'clickhouse_table': 'bronze.bpm_act_re_procdef'
        }
    ]
    
    print(f"{'表名':<25} {'MSSQL筆數':<15} {'ClickHouse筆數':<15} {'差異':<15} {'覆蓋率':<10}")
    print("-" * 80)
    
    total_mssql = 0
    total_clickhouse = 0
    
    for table_info in tables_to_check:
        try:
            # 查詢 MSSQL 總筆數
            mssql_count_sql = f"""
            SELECT count(*) FROM jdbc('mssql_master', '
                SELECT 1 FROM {table_info['mssql_table']}
            ')
            """
            
            print(f"正在查詢 {table_info['name']} MSSQL 筆數...")
            mssql_count = client.command(mssql_count_sql)
            
            # 查詢 ClickHouse 筆數
            try:
                clickhouse_count = client.command(f"SELECT count(*) FROM {table_info['clickhouse_table']}")
            except Exception as e:
                if "doesn't exist" in str(e).lower():
                    clickhouse_count = 0
                    print(f"⚠️ ClickHouse 表不存在: {table_info['clickhouse_table']}")
                else:
                    raise
            
            # 計算差異和覆蓋率
            diff = mssql_count - clickhouse_count
            coverage = (clickhouse_count / mssql_count * 100) if mssql_count > 0 else 0
            
            # 顯示結果
            status = "✅" if diff == 0 else "⚠️" if coverage > 90 else "❌"
            print(f"{status} {table_info['name']:<23} {mssql_count:<15,} {clickhouse_count:<15,} {diff:<15,} {coverage:<9.2f}%")
            
            total_mssql += mssql_count
            total_clickhouse += clickhouse_count
            
        except Exception as e:
            if "timeout" in str(e).lower():
                print(f"⚠️ {table_info['name']:<23} MSSQL查詢超時")
                
                # 只查詢 ClickHouse 筆數
                try:
                    clickhouse_count = client.command(f"SELECT count(*) FROM {table_info['clickhouse_table']}")
                    print(f"   ClickHouse筆數: {clickhouse_count:,}")
                except Exception as e2:
                    print(f"   ClickHouse查詢也失敗: {e2}")
            else:
                print(f"❌ {table_info['name']:<23} 查詢失敗: {e}")
    
    # 總計
    print("-" * 80)
    total_diff = total_mssql - total_clickhouse
    total_coverage = (total_clickhouse / total_mssql * 100) if total_mssql > 0 else 0
    print(f"{'總計':<25} {total_mssql:<15,} {total_clickhouse:<15,} {total_diff:<15,} {total_coverage:<9.2f}%")
    
    # 詳細分析
    print(f"\n📊 詳細分析:")
    print("-" * 60)
    
    if total_diff == 0:
        print("🎉 所有表格資料完全同步！")
    elif total_coverage > 95:
        print(f"✅ 整體同步狀況良好，覆蓋率 {total_coverage:.2f}%")
        print(f"   缺失 {total_diff:,} 筆資料")
    else:
        print(f"⚠️ 需要注意同步狀況，覆蓋率僅 {total_coverage:.2f}%")
        print(f"   缺失 {total_diff:,} 筆資料")
    
    # 檢查是否有表格不存在
    print(f"\n🔍 檢查 ClickHouse 表格存在性:")
    print("-" * 60)
    
    for table_info in tables_to_check:
        try:
            exists = client.command(f"EXISTS TABLE {table_info['clickhouse_table']}")
            if exists:
                print(f"✅ {table_info['clickhouse_table']}")
            else:
                print(f"❌ {table_info['clickhouse_table']} (不存在)")
        except Exception as e:
            print(f"❓ {table_info['clickhouse_table']} (檢查失敗: {e})")

if __name__ == "__main__":
    main()