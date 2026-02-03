import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    try:
        # Check if table exists and has data
        print("Checking gold.rmv_user_utilization...")
        res = client.query("SELECT count() FROM gold.rmv_user_utilization")
        count = res.result_rows[0][0]
        print(f"Total Rows: {count}")

        if count > 0:
            print("\nSample Data (First 5):")
            sample = client.query("SELECT * FROM gold.rmv_user_utilization LIMIT 5")
            for row in sample.result_rows:
                print(row)
                
            print("\nAggregated Stats by Vx:")
            stats = client.query("SELECT vx_type, sum(config_users), sum(active_users) FROM gold.rmv_user_utilization GROUP BY vx_type")
            print(f"{'Vx':<5} | {'Config':<10} | {'Active'}")
            print("-" * 30)
            for row in stats.result_rows:
                print(f"{row[0]:<5} | {row[1]:<10} | {row[2]}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
