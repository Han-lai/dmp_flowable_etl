#!/usr/bin/env python3
"""
資料庫初始化腳本
按順序執行所有 DDL 腳本，建立完整的資料庫結構
"""

import os
import sys
import time
import logging
from pathlib import Path
import clickhouse_connect

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# 專案根目錄
PROJECT_ROOT = Path(__file__).parent.parent.parent

# ClickHouse 連線設定
CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

# DDL 腳本執行順序
DDL_SCRIPTS = [
    "clickhouse/ddl/00_databases.sql",
    "clickhouse/ddl/10_bronze_sources.sql", 
    "clickhouse/ddl/20_silver_views_and_mviews.sql",
    "clickhouse/ddl/30_gold_views_and_mviews.sql",
    "clickhouse/ddl/40_validation_queries.sql"
]

def connect_clickhouse():
    """建立 ClickHouse 連線"""
    logger.info(f"連線 ClickHouse: {CLICKHOUSE_CONFIG['host']}:{CLICKHOUSE_CONFIG['port']}")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    client.command("SELECT 1")
    logger.info("ClickHouse 連線成功")
    return client

def execute_sql_file(client, sql_file_path):
    """執行 SQL 檔案"""
    full_path = PROJECT_ROOT / sql_file_path
    
    if not full_path.exists():
        logger.error(f"SQL 檔案不存在: {full_path}")
        return False
    
    logger.info(f"執行 SQL 檔案: {sql_file_path}")
    start_time = time.perf_counter()
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 分割多個 SQL 語句
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
        
        for i, statement in enumerate(statements, 1):
            if statement:
                logger.debug(f"執行語句 {i}/{len(statements)}")
                client.command(statement)
        
        duration = time.perf_counter() - start_time
        logger.info(f"✅ {sql_file_path} 執行完成，耗時 {duration:.2f} 秒")
        return True
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"❌ {sql_file_path} 執行失敗: {e}")
        return False

def main():
    """主程式"""
    logger.info("=" * 60)
    logger.info("開始初始化資料庫")
    logger.info("=" * 60)
    
    total_start = time.perf_counter()
    success_count = 0
    
    try:
        # 連線 ClickHouse
        client = connect_clickhouse()
        
        # 按順序執行 DDL 腳本
        for script in DDL_SCRIPTS:
            if execute_sql_file(client, script):
                success_count += 1
            else:
                logger.error(f"腳本執行失敗，停止初始化: {script}")
                sys.exit(1)
        
        total_duration = time.perf_counter() - total_start
        
        logger.info("=" * 60)
        logger.info("資料庫初始化完成")
        logger.info(f"成功執行 {success_count}/{len(DDL_SCRIPTS)} 個腳本")
        logger.info(f"總耗時: {total_duration:.2f} 秒")
        logger.info("=" * 60)
        
        # 執行驗收測試
        logger.info("執行驗收測試...")
        acceptance_test = "clickhouse/ddl/validation_acceptance_test.sql"
        if execute_sql_file(client, acceptance_test):
            logger.info("🎉 驗收測試通過！資料庫初始化成功！")
        else:
            logger.warning("⚠️ 驗收測試失敗，請檢查資料庫狀態")
            
    except Exception as e:
        logger.error(f"初始化過程發生錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()