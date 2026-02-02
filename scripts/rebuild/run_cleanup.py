"""
清理腳本: 執行 05_cleanup_path_a.sql - 備份並清理舊 Path A 表
"""
import clickhouse_connect

CH_CONFIG = {
    'host': '10.136.218.207',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

def run_cleanup():
    print("=" * 60)
    print("清理舊 Path A 表")
    print("=" * 60)
    
    client = clickhouse_connect.get_client(**CH_CONFIG)
    
    # 定義要備份的表
    tables_to_backup = [
        ("silver.FACT_TASK_VX_ATTRIBUTION", "silver.FACT_TASK_VX_ATTRIBUTION_backup_20260130"),
        ("silver.DIM_CONFIG_USER", "silver.DIM_CONFIG_USER_backup_20260130"),
        ("gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT", "gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_backup_20260130"),
        ("gold.DAILY_USER_UTILIZATION_SNAPSHOT", "gold.DAILY_USER_UTILIZATION_SNAPSHOT_backup_20260130"),
        ("gold.l5_dashboard_summary", "gold.l5_dashboard_summary_backup_20260130"),
    ]
    
    print("\n📦 1. 備份舊表（重命名）")
    print("-" * 40)
    
    for old_name, new_name in tables_to_backup:
        try:
            # 先檢查表是否存在
            db, table = old_name.split('.')
            check = client.query(f"SELECT count() FROM system.tables WHERE database='{db}' AND name='{table}'")
            if check.result_rows[0][0] == 0:
                print(f"  ⏭️  {old_name} 不存在，跳過")
                continue
            
            # 檢查備份表是否已存在
            _, backup_table = new_name.split('.')
            check_backup = client.query(f"SELECT count() FROM system.tables WHERE database='{db}' AND name='{backup_table}'")
            if check_backup.result_rows[0][0] > 0:
                print(f"  ⚠️  {new_name} 已存在，跳過")
                continue
            
            # 執行重命名 (ClickHouse 語法: RENAME TABLE old TO new)
            client.command(f"RENAME TABLE {old_name} TO {new_name}")
            print(f"  ✅ {old_name} → {new_name}")
        except Exception as e:
            print(f"  ❌ {old_name}: {e}")
    
    # 2. 移除舊 View
    print("\n🗑️  2. 移除舊 View")
    print("-" * 40)
    try:
        client.command("DROP VIEW IF EXISTS gold.v_l5_dashboard_summary_populate")
        print("  ✅ gold.v_l5_dashboard_summary_populate 已移除")
    except Exception as e:
        print(f"  ⚠️  {e}")
    
    # 3. 確認清理結果
    print("\n📋 3. 備份表清單")
    print("-" * 40)
    result = client.query("""
        SELECT database, name, engine
        FROM system.tables 
        WHERE (database = 'silver' OR database = 'gold')
          AND name LIKE '%backup%'
        ORDER BY database, name
    """)
    for row in result.result_rows:
        print(f"  📁 {row[0]}.{row[1]} ({row[2]})")
    
    print("\n" + "=" * 60)
    print("✅ Path A 清理完成！")
    print("=" * 60)
    print("\n💡 備份表將保留 7 天，之後可手動刪除")

if __name__ == '__main__':
    run_cleanup()
