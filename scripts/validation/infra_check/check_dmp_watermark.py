
import clickhouse_connect

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

try:
    print("Checking watermark for DMP tables...")
    result = client.query("SELECT * FROM bronze._sync_watermark WHERE table_name IN ('bronze.common_dmp_function_config', 'bronze.common_dmp_function_client_mapping') ORDER BY table_name")
    
    print(f"{'Table Name':<50} | {'Last Sync Time':<30} | {'Sync Time':<30} | {'Rows':<10}")
    print("-" * 130)
    for row in result.result_rows:
        table_name = row[0]
        last_sync = str(row[1])
        sync_time = str(row[2])
        rows = row[3]
        print(f"{table_name:<50} | {last_sync:<30} | {sync_time:<30} | {rows:<10}")
        
except Exception as e:
    print(f"Error checking watermark: {e}")
