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
        
        print("🔍 檢查 Silver 層原始資料 (Pivoted View)")
        print("-" * 60)
        
        sql = """
            SELECT 
                varinst_plant, 
                varinst_factory, 
                count(*) as count
            FROM silver.mv_varinst_pivoted 
            WHERE varinst_plant != '' OR varinst_factory != ''
            GROUP BY varinst_plant, varinst_factory 
            ORDER BY count DESC 
            LIMIT 5
        """
        
        result = client.query(sql)
        
        print(f"{'Varinst Plant':<15} | {'Varinst Factory':<15} | {'Count':<10}")
        print("-" * 60)
        
        for row in result.result_rows:
            plant, factory, count = row
            print(f"{plant:<15} | {factory:<15} | {count:<10}")

        print("\n🔍 檢查 MDM Line=E5 的詳細定義")
        sql_mdm = """
            SELECT line_name, plant_code, factory_code 
            FROM silver.dim_mfg_five_level 
            WHERE line_name='E5'
        """
        res_mdm = client.query(sql_mdm)
        for r in res_mdm.result_rows:
            print(f"MDM E5: PlantCode={r[1]}, FactoryCode={r[2]}")

    except Exception as e:
        print(f"查詢失敗: {e}")

if __name__ == "__main__":
    main()
