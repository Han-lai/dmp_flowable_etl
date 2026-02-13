
import clickhouse_connect
import pandas as pd
from datetime import datetime

# Connect to ClickHouse
client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

def get_bronze_status():
    print(f"{'Table Name':<40} | {'Rows':<10} | {'Last Sync (Max _extracted_at)':<30}")
    print("-" * 90)
    
    # Get list of tables
    tables = client.query("SELECT name FROM system.tables WHERE database = 'bronze' ORDER BY name").result_rows
    
    for (table_name,) in tables:
        try:
            # Get row count
            count = client.command(f"SELECT count() FROM bronze.{table_name}")
            
            # Get max _extracted_at if exists
            try:
                max_time = client.command(f"SELECT max(_extracted_at) FROM bronze.{table_name}")
                if isinstance(max_time, datetime):
                     last_sync = max_time.strftime("%Y-%m-%d %H:%M:%S")
                else:
                     last_sync = str(max_time)
                if last_sync == '1970-01-01 00:00:00': last_sync = 'N/A'
            except:
                last_sync = "N/A (No _extracted_at)"
            
            print(f"{table_name:<40} | {count:<10} | {last_sync:<30}")
            
        except Exception as e:
            print(f"{table_name:<40} | {'Error':<10} | {str(e)}")

if __name__ == "__main__":
    get_bronze_status()
