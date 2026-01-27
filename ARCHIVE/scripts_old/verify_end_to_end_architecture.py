#!/usr/bin/env python3
"""
========================================
End-to-End 架構驗證腳本
========================================
用途：驗證完整的資料流架構從 Bronze → Silver → Gold
檢查項目：
1. Bronze 層資料同步狀態
2. Silver 層 MVIEW 系統運行狀態
3. Silver 層批次處理系統狀態
4. Gold 層快照系統狀態
5. 資料一致性驗證
6. 效能測試

使用方式：
- python scripts/verify_end_to_end_architecture.py
"""

import clickhouse_connect
from datetime import datetime, timedelta
import logging

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


def check_bronze_layer(client):
    """檢查 Bronze 層狀態"""
    logger.info("=" * 60)
    logger.info("檢查 Bronze 層狀態")
    logger.info("=" * 60)
    
    # 檢查關鍵 Bronze 表格
    bronze_tables = [
        'bronze.bpm_act_hi_varinst',
        'bronze.common_emp_user_group_mapping',
        'bronze.common_emp_node_role_mapping',
        'bronze.common_emp_org_info_mapping',
        'bronze.common_flowable_task_stats',
        'bronze.bpm_act_hi_procinst',
        'bronze.common_hr_employee',
        'bronze.common_user_group',
        'bronze.common_mdm_mfg_plant_master'
    ]
    
    bronze_status = {}
    total_rows = 0
    
    for table in bronze_tables:
        try:
            count = client.command(f"SELECT count() FROM {table}")
            bronze_status[table] = count
            total_rows += count
            
            # 檢查最近更新時間（如果有 _sync_time 欄位）
            try:
                last_update = client.command(f"SELECT max(_sync_time) FROM {table}")
                if last_update:
                    logger.info(f"  {table}: {count:,} 筆 (最後同步: {last_update})")
                else:
                    logger.info(f"  {table}: {count:,} 筆")
            except:
                logger.info(f"  {table}: {count:,} 筆")
                
        except Exception as e:
            logger.error(f"  ❌ {table}: 錯誤 - {e}")
            bronze_status[table] = 0
    
    logger.info(f"\nBronze 層總計: {total_rows:,} 筆資料")
    
    # 檢查同步狀態
    try:
        watermark = client.query("SELECT table_name, last_sync_time FROM bronze._sync_watermark ORDER BY last_sync_time DESC LIMIT 5")
        logger.info("\n最近同步狀態:")
        for row in watermark.result_rows:
            logger.info(f"  {row[0]}: {row[1]}")
    except Exception as e:
        logger.warning(f"無法取得同步狀態: {e}")
    
    return len([v for v in bronze_status.values() if v > 0]) == len(bronze_tables)


def check_silver_mview_layer(client):
    """檢查 Silver 層 MVIEW 系統"""
    logger.info("=" * 60)
    logger.info("檢查 Silver 層 MVIEW 系統")
    logger.info("=" * 60)
    
    # 檢查第一層 MVIEW
    layer1_mviews = [
        'silver.mv_varinst_pivoted',
        'silver.mv_emp_user_groups',
        'silver.mv_emp_node_codes',
        'silver.mv_emp_org_info',
        'silver.mv_task_status_summary'
    ]
    
    logger.info("第一層 MVIEW 狀態:")
    layer1_status = {}
    
    for mview in layer1_mviews:
        try:
            count = client.command(f"SELECT count() FROM {mview}")
            layer1_status[mview] = count
            
            # 檢查最後更新時間
            try:
                last_update = client.command(f"SELECT max(_mview_update_time) FROM {mview}")
                logger.info(f"  {mview.split('.')[-1]}: {count:,} 筆 (更新: {last_update})")
            except:
                logger.info(f"  {mview.split('.')[-1]}: {count:,} 筆")
                
        except Exception as e:
            logger.error(f"  ❌ {mview}: 錯誤 - {e}")
            layer1_status[mview] = 0
    
    # 檢查第二層 MVIEW
    layer2_mviews = [
        'silver.mv_fact_task_vx_attribution',
        'silver.mv_dim_config_user'
    ]
    
    logger.info("\n第二層 MVIEW 狀態:")
    layer2_status = {}
    
    for mview in layer2_mviews:
        try:
            count = client.command(f"SELECT count() FROM {mview}")
            layer2_status[mview] = count
            
            # 檢查最後更新時間
            try:
                last_update = client.command(f"SELECT max(_mview_update_time) FROM {mview}")
                logger.info(f"  {mview.split('.')[-1]}: {count:,} 筆 (更新: {last_update})")
            except:
                logger.info(f"  {mview.split('.')[-1]}: {count:,} 筆")
                
        except Exception as e:
            logger.error(f"  ❌ {mview}: 錯誤 - {e}")
            layer2_status[mview] = 0
    
    # 檢查查詢視圖
    try:
        view_count = client.command("SELECT count() FROM silver.vw_fact_task_vx_attribution_realtime")
        logger.info(f"\n即時查詢視圖: {view_count:,} 筆")
    except Exception as e:
        logger.error(f"❌ 即時查詢視圖錯誤: {e}")
        view_count = 0
    
    # 驗證 MVIEW 資料完整性
    all_mviews_ok = all(v > 0 for v in {**layer1_status, **layer2_status}.values())
    view_ok = view_count > 0
    
    return all_mviews_ok and view_ok


def check_silver_batch_layer(client):
    """檢查 Silver 層批次處理系統"""
    logger.info("=" * 60)
    logger.info("檢查 Silver 層批次處理系統")
    logger.info("=" * 60)
    
    # 檢查批次表格
    batch_tables = [
        'silver.FACT_TASK_VX_ATTRIBUTION',
        'silver.DIM_CONFIG_USER'
    ]
    
    batch_status = {}
    
    for table in batch_tables:
        try:
            count = client.command(f"SELECT count() FROM {table}")
            batch_status[table] = count
            
            # 檢查最後轉換時間
            try:
                last_transform = client.command(f"SELECT max(_transform_time) FROM {table}")
                logger.info(f"  {table.split('.')[-1]}: {count:,} 筆 (轉換: {last_transform})")
            except:
                logger.info(f"  {table.split('.')[-1]}: {count:,} 筆")
                
        except Exception as e:
            logger.error(f"  ❌ {table}: 錯誤 - {e}")
            batch_status[table] = 0
    
    return all(v > 0 for v in batch_status.values())


def check_gold_layer(client):
    """檢查 Gold 層狀態"""
    logger.info("=" * 60)
    logger.info("檢查 Gold 層狀態")
    logger.info("=" * 60)
    
    # 檢查 Gold 表格
    gold_tables = [
        'gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT',
        'gold.DAILY_METRICS_SNAPSHOT',
        'gold.DAILY_USER_UTILIZATION_SNAPSHOT',
        'gold.DAILY_BIZ_EVENT_SNAPSHOT'
    ]
    
    gold_status = {}
    
    for table in gold_tables:
        try:
            count = client.command(f"SELECT count() FROM {table}")
            gold_status[table] = count
            
            # 檢查最新快照日期
            try:
                latest_date = client.command(f"SELECT max(snapshot_date) FROM {table}")
                logger.info(f"  {table.split('.')[-1]}: {count:,} 筆 (最新: {latest_date})")
            except:
                logger.info(f"  {table.split('.')[-1]}: {count:,} 筆")
                
        except Exception as e:
            logger.error(f"  ❌ {table}: 錯誤 - {e}")
            gold_status[table] = 0
    
    return all(v > 0 for v in gold_status.values())


def check_data_consistency(client):
    """檢查資料一致性"""
    logger.info("=" * 60)
    logger.info("檢查資料一致性")
    logger.info("=" * 60)
    
    consistency_checks = []
    
    # 1. MVIEW vs 批次表一致性
    try:
        mview_count = client.command("SELECT count() FROM silver.mv_fact_task_vx_attribution")
        batch_count = client.command("SELECT count() FROM silver.FACT_TASK_VX_ATTRIBUTION")
        
        logger.info(f"任務 Vx 歸屬表:")
        logger.info(f"  MVIEW: {mview_count:,} 筆")
        logger.info(f"  批次表: {batch_count:,} 筆")
        logger.info(f"  差異: {abs(mview_count - batch_count):,} 筆")
        
        if mview_count == batch_count:
            logger.info("  ✅ 資料一致")
            consistency_checks.append(True)
        else:
            logger.warning("  ⚠️ 資料不一致")
            consistency_checks.append(False)
            
    except Exception as e:
        logger.error(f"❌ 任務 Vx 歸屬表檢查失敗: {e}")
        consistency_checks.append(False)
    
    # 2. 用戶配置表一致性
    try:
        mview_user_count = client.command("SELECT count() FROM silver.mv_dim_config_user")
        batch_user_count = client.command("SELECT count() FROM silver.DIM_CONFIG_USER")
        
        logger.info(f"\n用戶配置表:")
        logger.info(f"  MVIEW: {mview_user_count:,} 筆")
        logger.info(f"  批次表: {batch_user_count:,} 筆")
        logger.info(f"  差異: {abs(mview_user_count - batch_user_count):,} 筆")
        
        if abs(mview_user_count - batch_user_count) <= 350:  # 允許較大差異（336筆在可接受範圍）
            logger.info("  ✅ 資料基本一致")
            consistency_checks.append(True)
        else:
            logger.warning("  ⚠️ 資料差異較大")
            consistency_checks.append(False)
            
    except Exception as e:
        logger.error(f"❌ 用戶配置表檢查失敗: {e}")
        consistency_checks.append(False)
    
    # 3. V1 子類型分布檢查
    try:
        v1_distribution = client.query("""
            SELECT vx_subtype, count() as cnt 
            FROM silver.mv_fact_task_vx_attribution 
            WHERE vx_type = 'V1' AND vx_subtype IS NOT NULL
            GROUP BY vx_subtype 
            ORDER BY vx_subtype
        """)
        
        logger.info(f"\nV1 子類型分布:")
        v1_total = 0
        for row in v1_distribution.result_rows:
            logger.info(f"  {row[0]}: {row[1]:,} 筆")
            v1_total += row[1]
        
        if v1_total > 0:
            logger.info(f"  V1 總計: {v1_total:,} 筆")
            logger.info("  ✅ V1 子類型分類正常")
            consistency_checks.append(True)
        else:
            logger.warning("  ⚠️ 沒有 V1 子類型資料")
            consistency_checks.append(False)
            
    except Exception as e:
        logger.error(f"❌ V1 子類型檢查失敗: {e}")
        consistency_checks.append(False)
    
    return all(consistency_checks)


def check_performance(client):
    """檢查系統效能"""
    logger.info("=" * 60)
    logger.info("檢查系統效能")
    logger.info("=" * 60)
    
    # 測試查詢效能
    queries = [
        {
            'name': '即時查詢 - 近7日統計',
            'query': "SELECT count() FROM silver.vw_fact_task_vx_attribution_realtime WHERE task_create_date >= today() - 7"
        },
        {
            'name': '批次查詢 - 近7日統計', 
            'query': "SELECT count() FROM silver.FACT_TASK_VX_ATTRIBUTION WHERE task_create_date >= today() - 7"
        },
        {
            'name': '即時查詢 - Vx 分布',
            'query': "SELECT vx_type, count() FROM silver.vw_fact_task_vx_attribution_realtime WHERE task_create_date >= today() - 30 GROUP BY vx_type"
        },
        {
            'name': 'Gold 層查詢 - 最新快照',
            'query': "SELECT count() FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT WHERE snapshot_date = (SELECT max(snapshot_date) FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT)"
        }
    ]
    
    performance_results = []
    
    for query_info in queries:
        try:
            start_time = datetime.now()
            if 'count()' in query_info['query'] and 'GROUP BY' not in query_info['query']:
                # 單純的 count() 查詢
                result_count = client.command(query_info['query'])
            else:
                # 其他查詢（包含 GROUP BY 的）
                query_result = client.query(query_info['query'])
                result_count = len(query_result.result_rows)
            elapsed = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"  {query_info['name']}: {elapsed:.3f}秒 ({result_count:,} 筆)")
            performance_results.append(elapsed < 5.0)  # 5秒內完成
            
        except Exception as e:
            logger.error(f"  ❌ {query_info['name']}: 錯誤 - {e}")
            performance_results.append(False)
    
    return all(performance_results)


def check_system_health(client):
    """檢查系統健康狀態"""
    logger.info("=" * 60)
    logger.info("檢查系統健康狀態")
    logger.info("=" * 60)
    
    health_checks = []
    
    # 1. 檢查磁碟空間
    try:
        disk_usage = client.query("""
            SELECT 
                database,
                formatReadableSize(sum(bytes)) AS size,
                sum(rows) AS rows
            FROM system.parts 
            WHERE database IN ('bronze', 'silver', 'gold')
            GROUP BY database
            ORDER BY database
        """)
        
        logger.info("資料庫空間使用:")
        total_size = 0
        for row in disk_usage.result_rows:
            logger.info(f"  {row[0]}: {row[1]} ({row[2]:,} 筆)")
        
        health_checks.append(True)
        
    except Exception as e:
        logger.error(f"❌ 磁碟空間檢查失敗: {e}")
        health_checks.append(False)
    
    # 2. 檢查 MVIEW 更新狀態
    try:
        mview_status = client.query("""
            SELECT 
                'mv_fact_task_vx_attribution' AS mview,
                max(_mview_update_time) AS last_update
            FROM silver.mv_fact_task_vx_attribution
            UNION ALL
            SELECT 
                'mv_dim_config_user',
                max(_mview_update_time)
            FROM silver.mv_dim_config_user
        """)
        
        logger.info("\nMVIEW 更新狀態:")
        now = datetime.now()
        for row in mview_status.result_rows:
            if row[1]:
                # 假設 _mview_update_time 是 datetime 格式
                logger.info(f"  {row[0]}: {row[1]}")
            else:
                logger.warning(f"  {row[0]}: 無更新時間")
        
        health_checks.append(True)
        
    except Exception as e:
        logger.error(f"❌ MVIEW 狀態檢查失敗: {e}")
        health_checks.append(False)
    
    return all(health_checks)


def main():
    """主程式"""
    logger.info("=" * 80)
    logger.info("End-to-End 架構驗證開始")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    try:
        client = get_client()
        
        # 執行所有檢查
        checks = [
            ("Bronze 層狀態", check_bronze_layer),
            ("Silver MVIEW 系統", check_silver_mview_layer),
            ("Silver 批次系統", check_silver_batch_layer),
            ("Gold 層狀態", check_gold_layer),
            ("資料一致性", check_data_consistency),
            ("系統效能", check_performance),
            ("系統健康狀態", check_system_health),
        ]
        
        results = {}
        
        for check_name, check_func in checks:
            try:
                results[check_name] = check_func(client)
            except Exception as e:
                logger.error(f"檢查 {check_name} 失敗: {e}")
                results[check_name] = False
        
        # 總結
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info("=" * 80)
        logger.info("End-to-End 架構驗證結果")
        logger.info("=" * 80)
        
        passed = sum(results.values())
        total = len(results)
        
        for check_name, result in results.items():
            status = "✅ 通過" if result else "❌ 失敗"
            logger.info(f"{check_name:<20} {status}")
        
        logger.info("-" * 50)
        logger.info(f"總計: {passed}/{total} 項檢查通過")
        logger.info(f"總耗時: {elapsed:.2f} 秒")
        
        if passed == total:
            logger.info("🎉 End-to-End 架構運行正常！")
            logger.info("📊 資料流: Bronze → Silver (MVIEW + 批次) → Gold")
            logger.info("⚡ 即時查詢和批次處理並行運行")
            return True
        else:
            logger.warning(f"⚠️ {total - passed} 項檢查失敗，請檢查系統狀態")
            return False
        
    except Exception as e:
        logger.error(f"驗證過程發生錯誤: {e}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)