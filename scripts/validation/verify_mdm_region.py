import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def verify_mdm_mapping():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    print("\n--- 🔍 檢查 MDM 廠別/區域 對應 (WJ2/NBU 相關) ---")
    query_map = """
    SELECT 
        FACTORY, 
        REGION,
        MFG_SITE
    FROM bronze.common_mdm_factory_area_master
    WHERE FACTORY IN ('WJ2', 'NBU', 'NPE', 'NBA', 'NBJ')
    """
    try:
        df_map = client.query_df(query_map)
        print("MDM Factory Area Mapping:")
        print(tabulate(df_map, headers='keys', tablefmt='psql', showindex=False))
    except Exception as e:
        print(f"Error: {e}")

    print("\n--- 🔍 檢查 Prod Area 關聯 (NBU) ---")
    query_pa = "SELECT PROD_AREA_ID, PROD_AREA_CODE, FACTORY, MFG_PLANT_ID FROM bronze.common_mdm_prod_area_master WHERE FACTORY IN ('WJ2', 'NBU') OR PROD_AREA_CODE IN ('WJ2', 'NBU')"
    try:
        df_pa = client.query_df(query_pa)
        print(tabulate(df_pa, headers='keys', tablefmt='psql', showindex=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_mdm_mapping()
