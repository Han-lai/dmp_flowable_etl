#!/usr/bin/env python3
"""
初始資料同步腳本
執行首次完整資料同步，建立所有 Bronze 層表格
"""

import os
import sys
import time
import logging
from pathlib import Path
import clickhouse_connect

# 加入專案路徑
sys.path.append(str(Path(__file__).parent.parent.parent))

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ClickHouse 連線設定
CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

# 要同步的表格設定
SYNC_TABLES = [
    # BPM 核心表 (增量同步表)
    {
        "source": "APP_SRV_BPM.dbo.ACT_HI_PROCINST",
        "target": "bronze.bpm_act_hi_procinst",
        "primary_key": "ID_",
        "tracking_col": "START_TIME_",
        "sync_type": "incremental"
    },
    {
        "source": "APP_SRV_BPM.dbo.ACT_HI_TASKINST", 
        "target": "bronze.bpm_act_hi_taskinst",
        "primary_key": "ID_",
        "tracking_col": "LAST_UPDATED_TIME_",
        "sync_type": "incremental"
    },
    {
        "source": "APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK",
        "target": "bronze.bpm_act_hi_identitylink", 
        "primary_key": "ID_",
        "tracking_col": "CREATE_TIME_",
        "sync_type": "incremental"
    },
    {
        "source": "APP_SRV_BPM.dbo.ACT_HI_VARINST",
        "target": "bronze.bpm_act_hi_varinst",
        "primary_key": "ID_",
        "tracking_col": "LAST_UPDATED_TIME_",
        "sync_type": "incremental"
    },
    
    # COMMON 表 (全量同步表)
    {
        "source": "APP_SRV_COMMON.dbo.FlowableTaskStats",
        "target": "bronze.common_flowable_task_stats",
        "primary_key": "Id",
        "tracking_col": "LastUpdatedTime",
        "sync_type": "incremental",
        "allow_nullable_key": True
    },
    {
        "source": "APP_SRV_BPM.dbo.ACT_RE_PROCDEF",
        "target": "bronze.bpm_act_re_procdef",
        "sync_type": "full"
    },
    {
        "source": "APP_SRV_COMMON.dbo.HR_Employee",
        "target": "bronze.common_hr_employee", 
        "sync_type": "full"
    },
    
    # MDM 主檔表
    {
        "source": "APP_SRV_COMMON.dbo.MDM_BU_ORG_TYPE_MASTER",
        "target": "bronze.common_mdm_bu_org_type_master",
        "sync_type": "full"
    },
    {
        "source": "APP_SRV_COMMON.dbo.MDM_MFG_SITE_MASTER", 
        "target": "bronze.common_mdm_mfg_site_master",
        "sync_type": "full"
    },
    {
        "source": "APP_SRV_COMMON.dbo.MDM_MFG_PLANT_MASTER",
        "target": "bronze.common_mdm_mfg_plant_master",
        "sync_type": "full"
    },
    {
        "source": "APP_SRV_COMMON.dbo.MDM_FACTORY_AREA_MASTER",
        "target": "bronze.common_mdm_factory_area_master", 
        "sync_type": "full"
    },
    {
        "source": "APP_SRV_COMMON.dbo.MDM_PROD_AREA_MASTER",
        "target": "bronze.common_mdm_prod_area_master",
        "sync_type": "full"
    },
    {
        "source": "APP_SRV_COMMON.dbo.MDM_LINE_DESC_MASTER",
        "target": "bronze.common_mdm_line_desc_master",
        "sync_type": "full"
    }
]

def connect_clickhouse():
    """建立 ClickHouse 連線"""
    logger.info(f"連線 ClickHouse: {CLICKHOUSE_CONFIG['host']}:{CLICKHOUSE_CONFIG['port']}")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    client.command("SELECT 1")
    logger.info("ClickHouse 連線成功")
    return client

def sync_incremental_table(client, config):
    """同步增量表 (建立 ReplacingMergeTree)"""
    source = config["source"]
    target = config["target"]
    pk = config["primary_key"]
    allow_nullable = config.get("allow_nullable_key", False)
    
    logger.info(f"同步增量表: {target}")
    start_time = time.perf_counter()
    
    try:
        # 刪除舊表
        client.command(f"DROP TABLE IF EXISTS {target}")
        
        # 建立新表
        settings = "SETTINGS allow_nullable_key = 1" if allow_nullable else ""
        
        create_sql = f"""
        CREATE TABLE {target}
        ENGINE = ReplacingMergeTree(_sync_time)
        ORDER BY ({pk})
        {settings}
        AS SELECT *, now64(3) as _sync_time 
        FROM jdbc('mssql_master', 'SELECT * FROM {source}')
        """
        
        client.command(create_sql)
        
        # 取得筆數
        row_count = client.command(f"SELECT count(*) FROM {target}")
        
        duration = time.perf_counter() - start_time
        logger.info(f"✅ {target} 同步完成: {row_count:,} 筆，耗時 {duration:.2f} 秒")
        
        return {"status": "success", "rows": row_count, "duration": duration}
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"❌ {target} 同步失敗: {e}")
        return {"status": "failed", "error": str(e), "duration": duration}

def sync_full_table(client, config):
    """同步全量表 (建立 MergeTree)"""
    source = config["source"]
    target = config["target"]
    
    logger.info(f"同步全量表: {target}")
    start_time = time.perf_counter()
    
    try:
        # 刪除舊表
        client.command(f"DROP TABLE IF EXISTS {target}")
        
        # 建立新表
        create_sql = f"""
        CREATE TABLE {target}
        ENGINE = MergeTree()
        ORDER BY tuple()
        AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM {source}')
        """
        
        client.command(create_sql)
        
        # 取得筆數
        row_count = client.command(f"SELECT count(*) FROM {target}")
        
        duration = time.perf_counter() - start_time
        logger.info(f"✅ {target} 同步完成: {row_count:,} 筆，耗時 {duration:.2f} 秒")
        
        return {"status": "success", "rows": row_count, "duration": duration}
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"❌ {target} 同步失敗: {e}")
        return {"status": "failed", "error": str(e), "duration": duration}

def setup_watermark_table(client):
    """建立 watermark 追蹤表"""
    logger.info("建立 watermark 追蹤表...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS bronze._sync_watermark (
        table_name String,
        last_sync_time DateTime64(3),
        sync_time DateTime64(3),
        row_count UInt64
    ) ENGINE = ReplacingMergeTree(sync_time)
    ORDER BY (table_name)
    """
    
    client.command(sql)
    logger.info("✅ Watermark 表建立完成")

def initialize_watermarks(client, results):
    """初始化 watermark 記錄"""
    logger.info("初始化 watermark 記錄...")
    
    for table_config, result in zip(SYNC_TABLES, results):
        if result["status"] == "success" and table_config.get("tracking_col"):
            target = table_config["target"]
            source = table_config["source"]
            tracking_col = table_config["tracking_col"]
            
            try:
                # 取得最大追蹤值
                max_sql = f"""
                SELECT * FROM jdbc('mssql_master', '
                    SELECT MAX({tracking_col}) FROM {source}
                ')
                """
                max_result = client.query(max_sql)
                
                if max_result.result_rows and max_result.result_rows[0][0]:
                    max_value = str(max_result.result_rows[0][0])
                    
                    # 插入 watermark
                    watermark_sql = f"""
                    INSERT INTO bronze._sync_watermark 
                    (table_name, last_sync_time, sync_time, row_count)
                    VALUES ('{target}', '{max_value}', now64(3), {result['rows']})
                    """
                    client.command(watermark_sql)
                    
                    logger.info(f"✅ {target} watermark 初始化: {max_value}")
                    
            except Exception as e:
                logger.warning(f"⚠️ {target} watermark 初始化失敗: {e}")

def main():
    """主程式"""
    logger.info("=" * 80)
    logger.info("開始初始資料同步")
    logger.info("=" * 80)
    
    total_start = time.perf_counter()
    results = []
    
    try:
        # 連線 ClickHouse
        client = connect_clickhouse()
        
        # 建立 watermark 表
        setup_watermark_table(client)
        
        # 同步所有表格
        for table_config in SYNC_TABLES:
            if table_config["sync_type"] == "incremental":
                result = sync_incremental_table(client, table_config)
            else:
                result = sync_full_table(client, table_config)
            
            results.append(result)
        
        # 初始化 watermark
        initialize_watermarks(client, results)
        
        # 統計結果
        total_duration = time.perf_counter() - total_start
        success_count = sum(1 for r in results if r["status"] == "success")
        total_rows = sum(r.get("rows", 0) for r in results if r["status"] == "success")
        
        logger.info("=" * 80)
        logger.info("初始資料同步完成")
        logger.info(f"成功同步: {success_count}/{len(SYNC_TABLES)} 張表")
        logger.info(f"總筆數: {total_rows:,}")
        logger.info(f"總耗時: {total_duration:.2f} 秒")
        logger.info("=" * 80)
        
        if success_count == len(SYNC_TABLES):
            logger.info("🎉 所有表格同步成功！")
        else:
            logger.warning("⚠️ 部分表格同步失敗，請檢查錯誤訊息")
            
    except Exception as e:
        logger.error(f"同步過程發生錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()