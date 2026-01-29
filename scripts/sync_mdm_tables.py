import clickhouse_connect
import logging
import time

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "bronze"
}

# 定義要同步的表對映關係 (Bronze Table -> MSSQL Source Table)
# 注意：使用 Create As Select (CAS) 模式自動建立表結構
TABLE_MAPPING = {
    "bronze.common_mdm_mfg_site_master": "APP_SRV_COMMON.dbo.MDM_MFG_SITE_MASTER",
    "bronze.common_mdm_mfg_plant_master": "APP_SRV_COMMON.dbo.MDM_MFG_PLANT_MASTER",
    "bronze.common_mdm_factory_area_master": "APP_SRV_COMMON.dbo.MDM_FACTORY_AREA_MASTER",
    "bronze.common_mdm_prod_area_master": "APP_SRV_COMMON.dbo.MDM_PROD_AREA_MASTER",
    "bronze.common_mdm_line_desc_master": "APP_SRV_COMMON.dbo.MDM_LINE_DESC_MASTER"
}

def sync_table(client, target_table, source_table):
    logger.info(f"🚀 Starting sync for: {target_table}")
    
    try:
        # 1. Drop existing table
        client.command(f"DROP TABLE IF EXISTS {target_table}")
        
        # 2. Create table and load data (Primary Key is omitted/tuple() for generic sync)
        # Using jdbc function to fetch data
        start_time = time.perf_counter()
        
        create_sql = f"""
        CREATE TABLE {target_table}
        ENGINE = MergeTree()
        ORDER BY tuple()
        AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM {source_table}')
        """
        
        client.command(create_sql)
        duration = time.perf_counter() - start_time
        
        # 3. Verify count
        count = client.command(f"SELECT count(*) FROM {target_table}")
        logger.info(f"✅ Synced {target_table}: {count} rows in {duration:.2f}s")
        
    except Exception as e:
        logger.error(f"❌ Failed to sync {target_table}: {e}")

def main():
    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        logger.info("Connected to ClickHouse.")
        
        for bronze_table, mssql_source in TABLE_MAPPING.items():
            sync_table(client, bronze_table, mssql_source)
            
        logger.info("🎉 All MDM tables sync completed.")
        
    except Exception as e:
        logger.error(f"Global Error: {e}")

if __name__ == "__main__":
    main()
