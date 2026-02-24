import clickhouse_connect
from datetime import datetime
import pandas as pd

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def check_sync_status():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("=" * 80)
    print("Bronze Layer Sync Status")
    print("=" * 80)
    
    # Check watermark table
    watermark_query = """
    SELECT 
        table_name,
        last_sync_time,
        sync_time,
        row_count
    FROM bronze._sync_watermark FINAL
    ORDER BY table_name
    """
    
    try:
        result = client.query(watermark_query)
        if result.result_rows:
            df = pd.DataFrame(result.result_rows, columns=['Table', 'Last Sync Time', 'Sync Time', 'Row Count'])
            print("\n📊 Watermark Status:")
            print(df.to_string(index=False))
        else:
            print("\n⚠️ No watermark records found")
    except Exception as e:
        print(f"\n❌ Error reading watermark: {e}")
    
    # Check actual table row counts
    print("\n" + "=" * 80)
    print("Actual Table Row Counts")
    print("=" * 80)
    
    tables = [
        "bronze.bpm_act_hi_taskinst",
        "bronze.bpm_act_hi_varinst",
        "bronze.bpm_act_hi_procinst",
        "bronze.bpm_act_hi_identitylink",
        "bronze.bpm_act_re_procdef",
        "bronze.common_hr_employee",
        "bronze.common_emp_node_role_mapping",
        "bronze.common_emp_org_info_mapping",
        "bronze.common_emp_user_group_mapping",
        "bronze.common_user_group",
        "bronze.common_process_role_user_mapping",
        "bronze.common_mdm_line_desc_master",
        "bronze.common_mdm_prod_area_master",
        "bronze.common_mdm_factory_area_master",
        "bronze.common_mdm_mfg_site_master",
        "bronze.common_mdm_mfg_plant_master"
    ]
    
    table_stats = []
    for table in tables:
        try:
            count = client.command(f"SELECT count() FROM {table}")
            table_stats.append((table.replace('bronze.', ''), f"{count:,}"))
        except Exception as e:
            table_stats.append((table.replace('bronze.', ''), f"Error: {str(e)[:50]}"))
    
    df_stats = pd.DataFrame(table_stats, columns=['Table', 'Row Count'])
    print("\n" + df_stats.to_string(index=False))

if __name__ == "__main__":
    check_sync_status()
