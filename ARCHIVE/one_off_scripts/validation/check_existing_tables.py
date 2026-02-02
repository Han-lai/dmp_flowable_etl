#!/usr/bin/env python3
"""
檢查 ClickHouse 現有表格狀態
"""

import clickhouse_connect

def check_tables():
    try:
        client = clickhouse_connect.get_client(
            host='REDACTED_IP',
            port=8121,
            username='default',
            password='default',
            database='default'
        )
        
        print("🔍 檢查現有表格狀態...")
        
        # 檢查各層級的表格
        for db in ['bronze', 'silver', 'gold']:
            print(f"\n📊 {db.upper()} 層表格:")
            try:
                tables = client.query(f'SHOW TABLES FROM {db}').result_rows
                if tables:
                    for table in tables:
                        table_name = table[0]
                        # 檢查表格記錄數
                        try:
                            count = client.query(f'SELECT COUNT(*) FROM {db}.{table_name}').result_rows[0][0]
                            print(f"  ✅ {table_name}: {count:,} 筆記錄")
                        except Exception as e:
                            print(f"  ⚠️ {table_name}: 無法查詢記錄數 ({e})")
                else:
                    print(f"  ❌ 無表格")
            except Exception as e:
                print(f"  ❌ 無法查詢 {db} 資料庫: {e}")
        
        # 檢查關鍵表格是否存在
        print(f"\n🎯 關鍵表格檢查:")
        key_tables = [
            ('bronze', 'bpm_act_hi_taskinst'),
            ('bronze', 'bpm_act_hi_varinst'),
            ('bronze', 'common_mdm_line_desc_master'),
            ('silver', 'mv_varinst_pivoted'),
            ('silver', 'dim_mfg_five_level'),
            ('silver', 'mv_fact_task_vx_attribution_mdm'),
            ('gold', 'l5_dashboard_summary')
        ]
        
        for db, table in key_tables:
            try:
                count = client.query(f'SELECT COUNT(*) FROM {db}.{table}').result_rows[0][0]
                print(f"  ✅ {db}.{table}: {count:,} 筆記錄")
            except Exception as e:
                print(f"  ❌ {db}.{table}: 不存在或無法查詢")
        
        return True
        
    except Exception as e:
        print(f"❌ 檢查失敗: {e}")
        return False

if __name__ == "__main__":
    check_tables()