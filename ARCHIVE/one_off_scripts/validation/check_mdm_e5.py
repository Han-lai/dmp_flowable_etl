import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        
        print("🔍 檢查 Silver MDM 五階維度 (Line=E5)")
        print("-" * 60)
        
        # 查詢 dim_mfg_five_level 中 E5 線的資料
        sql = """
            SELECT 
                line_name,
                factory_code, 
                factory_name,
                plant_code,
                plant_name,
                region_code
            FROM silver.dim_mfg_five_level
            WHERE line_name = 'E5'
        """
        
        result = client.query(sql)
        
        if result.result_rows:
            print(f"{'Line':<10} | {'Factory Code':<15} | {'Plant Code':<15} | {'Region':<10}")
            print("-" * 60)
            for row in result.result_rows:
                line, factory, factory_name, plant, plant_name, region = row
                print(f"{line:<10} | {factory:<15} | {plant:<15} | {region:<10}")
                print(f"Factory Name: {factory_name}")
                print(f"Plant Name: {plant_name}")
        else:
            print("❌ 找不到 E5 線的資料")
            
    except Exception as e:
        print(f"查詢失敗: {e}")

if __name__ == "__main__":
    main()
