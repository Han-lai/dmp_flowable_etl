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
        query = """
        SELECT final_vx_type, region_code, count() as cnt
        FROM silver.dim_config_users 
        GROUP BY final_vx_type, region_code 
        ORDER BY final_vx_type, region_code
        """
        result = client.query(query)
        print(f"{'Vx':<5} | {'Region':<10} | {'Count'}")
        print("-" * 30)
        for row in result.result_rows:
            print(f"{row[0]:<5} | {row[1]:<10} | {row[2]}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
