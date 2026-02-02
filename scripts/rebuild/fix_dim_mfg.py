"""
修復腳本: 重建 mv_dim_mfg_five_level
"""
import clickhouse_connect

CH_CONFIG = {
    'host': '10.136.218.207',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

FIX_SQL = """
DROP TABLE IF EXISTS silver.mv_dim_mfg_five_level;

CREATE MATERIALIZED VIEW silver.mv_dim_mfg_five_level
ENGINE = ReplacingMergeTree(_mview_update_time)
ORDER BY (line_name)
SETTINGS allow_nullable_key = 1
POPULATE AS
SELECT DISTINCT
    ld.LINE_NAME AS line_name,
    ld.LINE_DESC AS line_desc,
    pa.PROD_AREA_CODE AS prod_area_code,
    fa.FACTORY AS factory_code,
    fa.FACTORY_DESC AS factory_name,
    fa.PLANT_NODE AS plant_code,
    fa.PLANT_NODE_DESC AS plant_name,
    fa.REGION AS region_code,
    sm.MFG_SITE_DESC AS region_name,
    now64(3) AS _mview_update_time
FROM bronze.common_mdm_line_desc_master ld
LEFT JOIN bronze.common_mdm_prod_area_master pa ON ld.PROD_AREA_ID = pa.PROD_AREA_ID
LEFT JOIN bronze.common_mdm_factory_area_master fa ON pa.FACTORY = fa.FACTORY
LEFT JOIN bronze.common_mdm_mfg_site_master sm ON fa.MFG_SITE = sm.MFG_SITE
WHERE ld.LINE_NAME IS NOT NULL AND ld.LINE_NAME != ''
"""

def main():
    print("修復 mv_dim_mfg_five_level...")
    client = clickhouse_connect.get_client(**CH_CONFIG)
    
    # DROP
    print("1. DROP 舊表...")
    client.command("DROP TABLE IF EXISTS silver.mv_dim_mfg_five_level")
    print("   ✓ 完成")
    
    # CREATE
    print("2. CREATE 新表...")
    client.command(FIX_SQL.split(';')[1])
    print("   ✓ 完成")
    
    # 驗證
    print("3. 驗證...")
    result = client.query("SELECT count() FROM silver.mv_dim_mfg_five_level")
    count = result.result_rows[0][0]
    print(f"   ✓ mv_dim_mfg_five_level: {count} 筆")
    
    # 抽樣
    print("4. 抽樣資料...")
    sample = client.query("SELECT line_name, factory_code, plant_code, region_code FROM silver.mv_dim_mfg_five_level LIMIT 5")
    for row in sample.result_rows:
        print(f"   {row}")
    
    print("\n✓ 修復完成！")

if __name__ == '__main__':
    main()
