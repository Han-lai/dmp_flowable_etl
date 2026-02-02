import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        
        print("🔍 檢查 Silver 層 Plant/Factory 欄位值")
        print("-" * 60)
        
        sql = """
            SELECT 
                plant, 
                factory, 
                count(*) as count
            FROM silver.mv_fact_task_vx_attribution_mdm 
            WHERE plant != '' OR factory != ''
            GROUP BY plant, factory 
            ORDER BY count DESC 
            LIMIT 5
        """
        
        result = client.query(sql)
        
        print(f"{'Plant (廠區)':<15} | {'Factory (工廠)':<15} | {'Count':<10}")
        print("-" * 60)
        
        for row in result.result_rows:
            plant, factory, count = row
            print(f"{plant:<15} | {factory:<15} | {count:<10}")
            
    except Exception as e:
        print(f"查詢失敗: {e}")

if __name__ == "__main__":
    main()
