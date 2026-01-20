#!/usr/bin/env python3
"""
========================================
Silver 層 Materialized Views 建立腳本
========================================
用途：建立分層 MVIEW 架構，提供即時的 L5 指標計算能力
架構：
- 第一層：基礎聚合 MVIEW (GROUP BY 層)
- 第二層：業務邏輯 MVIEW (指標計算層)

使用方式：
- python scripts/create_silver_mviews.py                    # 建立所有 MVIEW
- python scripts/create_silver_mviews.py --layer 1         # 只建立第一層
- python scripts/create_silver_mviews.py --layer 2         # 只建立第二層
- python scripts/create_silver_mviews.py --drop-first      # 先刪除再建立

注意事項：
- 第二層依賴第一層，必須按順序建立
- 建立過程中會自動 POPULATE 歷史資料
- 不會影響現有的 FACT_TASK_VX_ATTRIBUTION 表
"""

import clickhouse_connect
from datetime import datetime
import logging
import argparse
import time

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ClickHouse 連線設定
CH_CONFIG = {
    'host': 'REDACTED_IP',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}


def get_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(**CH_CONFIG)


def execute_sql_file(client, sql_file_path):
    """執行 SQL 檔案"""
    logger.info(f"執行 SQL 檔案: {sql_file_path}")
    
    try:
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 分割 SQL 語句（以分號分隔）
        sql_statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
        
        for i, stmt in enumerate(sql_statements, 1):
            if stmt.upper().startswith('SELECT ') and 'status' in stmt.lower():
                # 執行狀態查詢並顯示結果
                result = client.query(stmt)
                if result.result_rows:
                    for row in result.result_rows:
                        logger.info(f"  {row}")
            else:
                # 執行其他語句
                try:
                    client.command(stmt)
                    logger.info(f"  執行語句 {i}/{len(sql_statements)}")
                except Exception as e:
                    logger.warning(f"  語句 {i} 執行警告: {e}")
        
        logger.info(f"SQL 檔案執行完成: {sql_file_path}")
        return True
        
    except Exception as e:
        logger.error(f"執行 SQL 檔案失敗 {sql_file_path}: {e}")
        return False


def check_dependencies(client):
    """檢查依賴的 Bronze 表是否存在"""
    logger.info("檢查 Bronze 層依賴表...")
    
    required_tables = [
        'bronze.bpm_act_hi_varinst',
        'bronze.common_emp_user_group_mapping',
        'bronze.common_user_group',
        'bronze.common_emp_node_role_mapping',
        'bronze.common_emp_org_info_mapping',
        'bronze.common_mdm_mfg_plant_master',
        'bronze.common_flowable_task_stats',
        'bronze.bpm_act_hi_procinst',
        'bronze.common_hr_employee'
    ]
    
    missing_tables = []
    
    for table in required_tables:
        try:
            result = client.command(f"EXISTS TABLE {table}")
            if result != 1:
                missing_tables.append(table)
        except Exception as e:
            logger.warning(f"檢查表 {table} 時發生錯誤: {e}")
            missing_tables.append(table)
    
    if missing_tables:
        logger.error("以下 Bronze 表不存在，請先執行 Bronze 同步:")
        for table in missing_tables:
            logger.error(f"  - {table}")
        return False
    
    logger.info("所有依賴表檢查通過")
    return True


def get_mview_status(client):
    """取得 MVIEW 狀態"""
    logger.info("檢查現有 MVIEW 狀態...")
    
    mview_tables = [
        # 第一層
        'silver.mv_varinst_pivoted',
        'silver.mv_emp_user_groups', 
        'silver.mv_emp_node_codes',
        'silver.mv_emp_org_info',
        'silver.mv_task_status_summary',
        # 第二層
        'silver.mv_fact_task_vx_attribution',
        'silver.mv_dim_config_user',
        'silver.mv_l5_metrics_realtime'
    ]
    
    status = {}
    
    for table in mview_tables:
        try:
            exists = client.command(f"EXISTS TABLE {table}")
            if exists:
                count = client.command(f"SELECT count() FROM {table}")
                status[table] = f"存在 ({count:,} 筆)"
            else:
                status[table] = "不存在"
        except Exception as e:
            status[table] = f"錯誤: {e}"
    
    logger.info("MVIEW 狀態:")
    for table, stat in status.items():
        logger.info(f"  {table}: {stat}")
    
    return status


def drop_layer2_mviews(client):
    """刪除第二層 MVIEW（依賴順序）"""
    logger.info("刪除第二層 MVIEW...")
    
    layer2_objects = [
        'silver.vw_fact_task_vx_attribution_realtime',  # 視圖先刪
        'silver.mv_l5_metrics_realtime',
        'silver.mv_dim_config_user', 
        'silver.mv_fact_task_vx_attribution'
    ]
    
    for obj in layer2_objects:
        try:
            if 'vw_' in obj:
                client.command(f"DROP VIEW IF EXISTS {obj}")
                logger.info(f"  刪除視圖: {obj}")
            else:
                client.command(f"DROP TABLE IF EXISTS {obj}")
                logger.info(f"  刪除表: {obj}")
        except Exception as e:
            logger.warning(f"刪除 {obj} 時發生錯誤: {e}")


def drop_layer1_mviews(client):
    """刪除第一層 MVIEW"""
    logger.info("刪除第一層 MVIEW...")
    
    layer1_tables = [
        'silver.mv_task_status_summary',
        'silver.mv_emp_org_info',
        'silver.mv_emp_node_codes',
        'silver.mv_emp_user_groups',
        'silver.mv_varinst_pivoted'
    ]
    
    for table in layer1_tables:
        try:
            client.command(f"DROP TABLE IF EXISTS {table}")
            logger.info(f"  刪除表: {table}")
        except Exception as e:
            logger.warning(f"刪除 {table} 時發生錯誤: {e}")


def create_layer1(client):
    """建立第一層 MVIEW"""
    logger.info("=" * 60)
    logger.info("建立第一層 MVIEW (基礎聚合層)")
    logger.info("=" * 60)
    
    return execute_sql_file(client, 'sql/11_create_silver_mviews_layer1.sql')


def create_layer2(client):
    """建立第二層 MVIEW"""
    logger.info("=" * 60)
    logger.info("建立第二層 MVIEW (業務邏輯層)")
    logger.info("=" * 60)
    
    return execute_sql_file(client, 'sql/12_create_silver_mviews_layer2.sql')


def main():
    """主程式"""
    parser = argparse.ArgumentParser(description='Silver 層 Materialized Views 建立腳本')
    parser.add_argument('--layer', type=int, choices=[1, 2], 
                        help='指定建立的層級：1=第一層, 2=第二層')
    parser.add_argument('--drop-first', action='store_true',
                        help='建立前先刪除現有 MVIEW')
    parser.add_argument('--check-only', action='store_true',
                        help='只檢查狀態，不執行建立')
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("Silver 層 Materialized Views 建立腳本")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    try:
        client = get_client()
        
        # 檢查依賴
        if not check_dependencies(client):
            return False
        
        # 檢查現有狀態
        get_mview_status(client)
        
        if args.check_only:
            logger.info("僅檢查模式，結束執行")
            return True
        
        # 刪除現有 MVIEW（如果指定）
        if args.drop_first:
            logger.info("刪除現有 MVIEW...")
            drop_layer2_mviews(client)  # 先刪第二層
            drop_layer1_mviews(client)  # 再刪第一層
        
        success = True
        
        # 建立第一層
        if args.layer is None or args.layer == 1:
            if not create_layer1(client):
                success = False
        
        # 建立第二層（需要第一層完成）
        if success and (args.layer is None or args.layer == 2):
            if not create_layer2(client):
                success = False
        
        if success:
            logger.info("=" * 60)
            logger.info("MVIEW 建立完成！檢查最終狀態...")
            get_mview_status(client)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info("=" * 60)
            logger.info(f"所有 MVIEW 建立成功！總耗時: {elapsed:.2f} 秒")
            logger.info("=" * 60)
            logger.info("使用方式:")
            logger.info("  即時查詢: SELECT * FROM silver.vw_fact_task_vx_attribution_realtime")
            logger.info("  批次查詢: SELECT * FROM silver.FACT_TASK_VX_ATTRIBUTION")
            logger.info("  L5 即時指標: SELECT * FROM silver.mv_l5_metrics_realtime")
            logger.info("=" * 60)
        else:
            logger.error("MVIEW 建立過程中發生錯誤")
            return False
        
    except Exception as e:
        logger.error(f"執行失敗: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)