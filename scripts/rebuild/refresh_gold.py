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
    print("Triggering refresh for gold.rmv_user_utilization...")
    try:
        client.command("SYSTEM REFRESH VIEW gold.rmv_user_utilization")
        print("Refresh triggered.")
        
        # Verify plant codes in Gold
        print("\nChecking Gold Plant Codes (Sample):")
        res = client.query("SELECT DISTINCT plant_code FROM gold.rmv_user_utilization LIMIT 10")
        for row in res.result_rows:
            print(row[0])
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
