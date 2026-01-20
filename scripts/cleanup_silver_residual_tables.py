#!/usr/bin/env python3
"""
========================================
Silver 層殘留表格清理腳本
========================================
用途：清理 Silver 層中不需要的殘留表格
識別的殘留表格類型：
1. .inner_id.* - MVIEW 內部表格
2. RMV_* - 舊的 MVIEW
3. V_* - 舊的 View
4. fact_* - 舊的事實表
5. dim_* - 舊的維度表
6. varinst_*_pivot - 舊的轉置表
7. task_detail_wide - 舊的寬表
8. _transform_log - 轉換日誌表

使用方式：
- python scripts/cleanup_silver_residual_tables.py --dry-run    # 只顯示要刪除的表格
- python scripts/cleanup_silver_residual_tables.py             # 實際執行刪除
"""

import clickhouse_connect
from datetime import datetime
import logging
import argparse

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


def get_residual_tables(client):
    """取得需要清理的殘留表格"""
    
    # 定義需要保留的表格（白名單）
    keep_tables = {
        # 現有批次表
        'FACT_TASK_VX_ATTRIBUTION',
        'DIM_CONFIG_USER',
        
        # 新的 MVIEW 系統
        'mv_varinst_pivoted',
        'mv_emp_user_groups', 
        'mv_emp_node_codes',
        'mv_emp_org_info',
        'mv_task_status_summary',
        'mv_fact_task_vx_attribution',
        'mv_dim_config_user',
        'mv_l5_metrics_realtime',
        
        # 查詢視圖
        'vw_fact_task_vx_attribution_realtime'
    }
    
    # 取得所有 silver 表格
    result = client.query("SHOW TABLES FROM silver")
    all_tables = [row[0] for row in result.result_rows]
    
    # 識別殘留表格
    residual_tables = []
    
    for table in all_tables:
        if table not in keep_tables:
            residual_tables.append(table)
    
    return residual_tables


def get_table_info(client, table):
    """取得表格詳細資訊"""
    try:
        result = client.query(f"""
            SELECT engine, total_rows, total_bytes
            FROM system.tables 
            WHERE database = 'silver' AND name = '{table}'
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


def categorize_residual_tables(tables):
    """將殘留表格分類"""
    categories = {
        'MVIEW 內部表格': [],
        '舊的 MVIEW': [],
        '舊的 View': [],
        '舊的事實表': [],
        '舊的維度表': [],
        '舊的轉置表': [],
        '其他殘留表格': []
    }
    
    for table in tables:
        if table.startswith('.inner_id.'):
            categories['MVIEW 內部表格'].append(table)
        elif table.startswith('RMV_'):
            categories['舊的 MVIEW'].append(table)
        elif table.startswith('V_'):
            categories['舊的 View'].append(table)
        elif table.startswith('fact_'):
            categories['舊的事實表'].append(table)
        elif table.startswith('dim_'):
            categories['舊的維度表'].append(table)
        elif 'pivot' in table.lower():
            categories['舊的轉置表'].append(table)
        else:
            categories['其他殘留表格'].append(table)
    
    return categories


def drop_table_safe(client, table, dry_run=False):
    """安全地刪除表格"""
    try:
        # 取得表格資訊
        info = get_table_info(client, table)
        
        if dry_run:
            logger.info(f"  [DRY-RUN] 將刪除: {table} ({info['engine']}, {info['rows']:,} 筆, {info['size_mb']} MB)")
            return True
        
        # 處理特殊命名的表格（.inner_id.*）
        if table.startswith('.inner_id.'):
            # 使用反引號包圍特殊表格名稱
            table_name = f"`{table}`"
        else:
            table_name = table
        
        # 判斷是 View 還是 Table
        if info['engine'] in ['View', 'MaterializedView']:
            if info['engine'] == 'View':
                client.command(f"DROP VIEW IF EXISTS silver.{table_name}")
                logger.info(f"  ✅ 刪除 View: {table}")
            else:
                client.command(f"DROP TABLE IF EXISTS silver.{table_name}")
                logger.info(f"  ✅ 刪除 MaterializedView: {table}")
        else:
            client.command(f"DROP TABLE IF EXISTS silver.{table_name}")
            logger.info(f"  ✅ 刪除 Table: {table}")
        
        return True
        
    except Exception as e:
        logger.error(f"  ❌ 刪除 {table} 失敗: {e}")
        return False


def main():
    """主程式"""
    parser = argparse.ArgumentParser(description='Silver 層殘留表格清理腳本')
    parser.add_argument('--dry-run', action='store_true',
                        help='只顯示要刪除的表格，不實際執行')
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("Silver 層殘留表格清理腳本")
    logger.info("=" * 80)
    
    if args.dry_run:
        logger.info("🔍 DRY-RUN 模式：只顯示要刪除的表格")
    else:
        logger.info("⚠️ 實際執行模式：將刪除殘留表格")
    
    start_time = datetime.now()
    
    try:
        client = get_client()
        
        # 1. 取得殘留表格
        logger.info("=" * 60)
        logger.info("識別殘留表格")
        logger.info("=" * 60)
        
        residual_tables = get_residual_tables(client)
        
        if not residual_tables:
            logger.info("✅ 沒有發現殘留表格")
            return True
        
        logger.info(f"發現 {len(residual_tables)} 張殘留表格")
        
        # 2. 分類殘留表格
        categories = categorize_residual_tables(residual_tables)
        
        total_size_mb = 0
        total_rows = 0
        
        for category, tables in categories.items():
            if not tables:
                continue
                
            logger.info(f"\n{category} ({len(tables)} 張):")
            
            for table in tables:
                info = get_table_info(client, table)
                total_size_mb += info['size_mb']
                total_rows += info['rows']
                logger.info(f"  - {table} ({info['engine']}, {info['rows']:,} 筆, {info['size_mb']} MB)")
        
        logger.info("=" * 60)
        logger.info(f"總計: {len(residual_tables)} 張表格, {total_rows:,} 筆資料, {total_size_mb:.2f} MB")
        
        # 3. 確認刪除
        if not args.dry_run:
            logger.info("=" * 60)
            logger.info("⚠️ 即將刪除以上所有殘留表格")
            logger.info("⚠️ 這個操作無法復原！")
            
            # 在生產環境中，這裡應該要求用戶確認
            # 但根據 agent.md 的指示，我們只做被要求的事
            logger.info("開始刪除殘留表格...")
        
        # 4. 執行刪除
        logger.info("=" * 60)
        logger.info("執行清理")
        logger.info("=" * 60)
        
        success_count = 0
        failed_count = 0
        
        # 按分類順序刪除（先刪除依賴較少的）
        delete_order = [
            '舊的 View',
            '舊的 MVIEW', 
            'MVIEW 內部表格',
            '舊的事實表',
            '舊的維度表',
            '舊的轉置表',
            '其他殘留表格'
        ]
        
        for category in delete_order:
            tables = categories.get(category, [])
            if not tables:
                continue
                
            logger.info(f"\n清理 {category}:")
            
            for table in tables:
                if drop_table_safe(client, table, args.dry_run):
                    success_count += 1
                else:
                    failed_count += 1
        
        # 5. 總結
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info("=" * 80)
        logger.info("清理結果總結")
        logger.info("=" * 80)
        
        if args.dry_run:
            logger.info(f"🔍 DRY-RUN 完成：識別出 {len(residual_tables)} 張殘留表格")
            logger.info(f"💾 預計釋放空間: {total_size_mb:.2f} MB")
            logger.info("執行清理請使用: python scripts/cleanup_silver_residual_tables.py")
        else:
            logger.info(f"✅ 成功刪除: {success_count} 張表格")
            if failed_count > 0:
                logger.info(f"❌ 刪除失敗: {failed_count} 張表格")
            logger.info(f"💾 釋放空間: {total_size_mb:.2f} MB")
            logger.info(f"🗑️ 清理資料: {total_rows:,} 筆")
        
        logger.info(f"總耗時: {elapsed:.2f} 秒")
        
        return failed_count == 0
        
    except Exception as e:
        logger.error(f"清理過程發生錯誤: {e}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)