import clickhouse_connect
import pandas as pd
from tabulate import tabulate

def show_mapping():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    
    print("--- 🔍 五階維度 (mv_dim_mfg_five_level) 對應明細 ---")
    query = """
    SELECT 
        factory_code, 
        factory_name, 
        plant_code, 
        region_code, 
        region_name
    FROM silver.mv_dim_mfg_five_level
    WHERE plant_code = 'WJ2' AND factory_code IN ('NBU', 'NPE', 'NBA', 'NBJ')
    LIMIT 20
    """
    try:
        df = client.query_df(query)
        print(tabulate(df, headers='keys', tablefmt='psql', showindex=False))
    except Exception as e:
        print(f"Error: {e}")

    print("\n--- 🔍 MDM 來源表 (common_mdm_factory_area_master) 明細 ---")
    # We need to know which FACTORY in FA corresponds to these
    # In mv_dim_mfg_five_level: pa.FACTORY = fa.FACTORY
    # Let's find pa.FACTORY for these NBU/NPE
    query_pa = """
    SELECT DISTINCT
        pa.PROD_AREA_CODE,
        pa.FACTORY as fa_join_key,
        fa.REGION as mdm_region_field,
        fa.MFG_SITE as mdm_mfg_site_field
    FROM bronze.common_mdm_prod_area_master pa
    LEFT JOIN bronze.common_mdm_factory_area_master fa ON pa.FACTORY = fa.FACTORY
    WHERE pa.PROD_AREA_CODE IN ('WJ2_NBU_MAIN', 'WJ2_NPE_MAIN', 'WJ2_NBA_MAIN', 'WJ2_NBJ_MAIN')
       OR pa.FACTORY IN ('WJ2', 'NBU', 'NPE')
    """
    try:
        df_pa = client.query_df(query_pa)
        print(tabulate(df_pa, headers='keys', tablefmt='psql', showindex=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    show_mapping()
