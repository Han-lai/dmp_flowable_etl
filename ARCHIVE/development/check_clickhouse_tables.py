#!/usr/bin/env python3
"""
========================================
ClickHouse 表格檢查腳本
========================================
用途：檢查 ClickHouse 中所有表格，特別是 silver 層的表格
識別：
1. 所有 database 和表格
2. silver 層中的表格分類
3. 識別可能的殘留表格

使用方式：
- python scripts/check_clickhouse_tables.py
"""

import clickhouse_connect
from datetime import datetime
import logging

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ClickHouse 連線設定
CH_CONFIG = {
    'host': '10.136.218.207',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}


def get_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(**CH_CONFIG)


def get_all_databases(client):
    """取得所有 database"""
    logger.info("=" * 60)
    logger.info("檢查所有 Database")
    logger.info("=" * 60)
    
    result = client.query("SHOW DATABASES")
    databases = [row[0] for row in result.result_rows]
    
    for db in sorted(databases):
        logger.info(f"  {db}")
    
    return databases


def get_tables_in_database(client, database):
    """取得指定 database 中的所有表格"""
    try:
        result = client.query(f"SHOW TABLES FROM {database}")
        tables = [row[0] for row in result.result_rows]
        return tables
    except Exception as e:
        logger.warning(f"無法取得 {database} 的表格: {e}")
        return []


def get_table_info(client, database, table):
    """取得表格詳細資訊"""
    try:
        # 取得表格類型和引擎
        result = client.query(f"""
            SELECT engine, total_rows, total_bytes
            FROM system.tables 
            WHERE database = '{database}' AND name = '{table}'
        """)
        
        if result.result_rows:
            engine, rows, bytes_size = result.result_rows[0]
            size_mb = bytes_size / (1024 * 1024) if bytes_size else 0
            return {
                'engine': engine,
                'rows': rows or 0,
                'size_mb': round(size_mb, 2)
            }
        else:
            return {'engine': 'Unknown', 'rows': 0, 'size_mb': 0}
    except Exception as e:
        return {'engine': 'Error', 'rows': 0, 'size_mb': 0}


def analyze_silver_tables(client):
    """分析 silver 層表格"""
    logger.info("=" * 60)
    logger.info("分析 Silver 層表格")
    logger.info("=" * 60)
    
    tables = get_tables_in_database(client, 'silver')
    
    if not tables:
        logger.warning("silver database 不存在或沒有表格")
        return
    
    # 定義已知的表格分類
    known_categories = {
        'MVIEW 第一層': [
            'mv_varinst_pivoted',
            'mv_emp_user_groups', 
            'mv_emp_node_codes',
            'mv_emp_org_info',
            'mv_task_status_summary'
        ],
        'MVIEW 第二層': [
            'mv_fact_task_vx_attribution',
            'mv_dim_config_user',
            'mv_l5_metrics_realtime'
        ],
        '查詢視圖': [
            'vw_fact_task_vx_attribution_realtime'
        ],
        '現有批次表': [
            'FACT_TASK_VX_ATTRIBUTION',
            'DIM_CONFIG_USER'
        ]
    }
    
    # 收集所有已知表格
    all_known_tables = set()
    for category_tables in known_categories.values():
        all_known_tables.update(category_tables)
    
    # 分析每個表格
    table_analysis = {}
    
    for table in sorted(tables):
        info = get_table_info(client, 'silver', table)
        table_analysis[table] = info
        
        # 判斷表格分類
        category = '未知/可能殘留'
        for cat_name, cat_tables in known_categories.items():
            if table in cat_tables:
                category = cat_name
                break
        
        logger.info(f"  {table}")
        logger.info(f"    分類: {category}")
        logger.info(f"    引擎: {info['engine']}")
        logger.info(f"    筆數: {info['rows']:,}")
        logger.info(f"    大小: {info['size_mb']} MB")
        logger.info("")
    
    # 識別可能的殘留表格
    logger.info("=" * 60)
    logger.info("可能的殘留表格分析")
    logger.info("=" * 60)
    
    residual_tables = []
    for table in tables:
        if table not in all_known_tables:
            residual_tables.append(table)
    
    if residual_tables:
        logger.info("發現可能的殘留表格:")
        for table in residual_tables:
            info = table_analysis[table]
            logger.info(f"  {table} - {info['engine']} - {info['rows']:,} 筆 - {info['size_mb']} MB")
        
        logger.info("")
        logger.info("建議檢查這些表格是否需要保留:")
        for table in residual_tables:
            logger.info(f"  - {table}: 檢查用途和最後更新時間")
    else:
        logger.info("✅ 沒有發現殘留表格，所有表格都有明確用途")
    
    return residual_tables


def check_table_dependencies(client, table_name):
    """檢查表格的依賴關係"""
    logger.info(f"檢查表格 {table_name} 的依賴關係...")
    
    try:
        # 檢查是否有其他表格依賴此表格
        result = client.query(f"""
            SELECT DISTINCT table, database
            FROM system.tables 
            WHERE engine LIKE '%MaterializedView%'
        """)
        
        # 這裡可以進一步檢查 MVIEW 的定義
        # 但 ClickHouse 的 system.tables 不直接提供依賴資訊
        logger.info(f"  需要手動檢查 {table_name} 是否被其他 MVIEW 使用")
        
    except Exception as e:
        logger.warning(f"檢查依賴關係時發生錯誤: {e}")


def main():
    """主程式"""
    logger.info("=" * 80)
    logger.info("ClickHouse 表格檢查開始")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    try:
        client = get_client()
        
        # 1. 檢查所有 database
        databases = get_all_databases(client)
        
        # 2. 檢查每個 database 的表格數量
        logger.info("=" * 60)
        logger.info("各 Database 表格統計")
        logger.info("=" * 60)
        
        for db in sorted(databases):
            if db not in ['system', 'information_schema', 'INFORMATION_SCHEMA']:
                tables = get_tables_in_database(client, db)
                logger.info(f"  {db}: {len(tables)} 張表格")
                
                # 列出前幾個表格名稱
                if tables:
                    sample_tables = tables[:5]
                    logger.info(f"    範例: {', '.join(sample_tables)}")
                    if len(tables) > 5:
                        logger.info(f"    ... 還有 {len(tables) - 5} 張表格")
        
        # 3. 重點分析 silver 層
        residual_tables = analyze_silver_tables(client)
        
        # 4. 總結
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info("=" * 80)
        logger.info("檢查結果總結")
        logger.info("=" * 80)
        
        if residual_tables:
            logger.info(f"發現 {len(residual_tables)} 張可能的殘留表格")
            logger.info("建議進一步檢查這些表格的用途")
        else:
            logger.info("✅ Silver 層表格結構正常，沒有發現殘留表格")
        
        logger.info(f"總耗時: {elapsed:.2f} 秒")
        
        return True
        
    except Exception as e:
        logger.error(f"檢查過程發生錯誤: {e}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)