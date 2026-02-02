#!/usr/bin/env python3
"""
檢查 BPM 表的 MSSQL vs ClickHouse 資料量比較 (快速版 - 排除大表)
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
    
    print("🔍 檢查 BPM 表資料量比較 (快速版)")
    print("=" * 80)
    
    # 定義要檢查的表格對應關係 (排除 IDENTITYLINK)
    tables_to_check = [
        # {
        #     'name': 'ACT_HI_IDENTITYLINK_0108',
        #     'mssql_table': 'APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0108',
        #     'clickhouse_table': 'bronze.bpm_act_hi_identitylink'
        # },
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
            
            print(f"正在查詢 {table_info['name']}...", end="", flush=True)
            mssql_count = client.command(mssql_count_sql)
            
            # 查詢 ClickHouse 筆數
            try:
                clickhouse_count = client.command(f"SELECT count(*) FROM {table_info['clickhouse_table']}")
            except Exception as e:
                clickhouse_count = 0
                print(f"\n⚠️ ClickHouse 表不存在: {table_info['clickhouse_table']}")
            
            # 計算差異和覆蓋率
            diff = mssql_count - clickhouse_count
            coverage = (clickhouse_count / mssql_count * 100) if mssql_count > 0 else 0
            
            # 顯示結果
            print(f"\r", end="")
            status = "✅" if diff == 0 else "⚠️" if coverage > 90 else "❌"
            print(f"{status} {table_info['name']:<23} {mssql_count:<15,} {clickhouse_count:<15,} {diff:<15,} {coverage:<9.2f}%")
            
            total_mssql += mssql_count
            total_clickhouse += clickhouse_count
            
        except Exception as e:
            print(f"\n❌ {table_info['name']:<23} 查詢失敗: {e}")
    
    # 總計
    print("-" * 80)
    total_diff = total_mssql - total_clickhouse
    total_coverage = (total_clickhouse / total_mssql * 100) if total_mssql > 0 else 0
    print(f"{'總計':<25} {total_mssql:<15,} {total_clickhouse:<15,} {total_diff:<15,} {total_coverage:<9.2f}%")

if __name__ == "__main__":
    main()
