#!/usr/bin/env python3
"""
========================================
MVIEW 系統驗證腳本
========================================
用途：驗證 MVIEW 系統與現有批次系統的資料一致性
檢查項目：
1. 資料筆數一致性
2. Vx 歸屬邏輯一致性
3. 排除邏輯一致性
4. V1 子類型邏輯一致性
5. 即時查詢效能測試

使用方式：
- python scripts/verify_mview_system.py
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
    'host': 'REDACTED_IP',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}


def get_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(**CH_CONFIG)


def test_data_consistency(client):
    """測試資料一致性"""
    logger.info("=" * 60)
    logger.info("測試資料一致性")
    logger.info("=" * 60)
    
    # 1. 總筆數比較
    mview_count = client.command("SELECT count() FROM silver.mv_fact_task_vx_attribution")
    batch_count = client.command("SELECT count() FROM silver.FACT_TASK_VX_ATTRIBUTION")
    
    logger.info(f"MVIEW 總筆數: {mview_count:,}")
    logger.info(f"批次表總筆數: {batch_count:,}")
    logger.info(f"差異: {abs(mview_count - batch_count):,}")
    
    if mview_count == batch_count:
        logger.info("✅ 總筆數一致")
    else:
        logger.warning("⚠️ 總筆數不一致")
    
    return mview_count == batch_count


def test_vx_attribution(client):
    """測試 Vx 歸屬邏輯"""
    logger.info("=" * 60)
    logger.info("測試 Vx 歸屬邏輯")
    logger.info("=" * 60)
    
    # Vx 分布比較
    mview_vx = client.query("""
        SELECT vx_type, count() as cnt 
        FROM silver.mv_fact_task_vx_attribution 
        GROUP BY vx_type 
        ORDER BY vx_type
    """)
    
    batch_vx = client.query("""
        SELECT vx_type, count() as cnt 
        FROM silver.FACT_TASK_VX_ATTRIBUTION 
        GROUP BY vx_type 
        ORDER BY vx_type
    """)
    
    logger.info("Vx 分布比較:")
    logger.info("類型     MVIEW筆數    批次筆數     差異")
    logger.info("-" * 50)
    
    mview_dict = {row[0]: row[1] for row in mview_vx.result_rows}
    batch_dict = {row[0]: row[1] for row in batch_vx.result_rows}
    
    all_vx_types = set(mview_dict.keys()) | set(batch_dict.keys())
    all_consistent = True
    
    for vx_type in sorted(all_vx_types):
        mview_cnt = mview_dict.get(vx_type, 0)
        batch_cnt = batch_dict.get(vx_type, 0)
        diff = abs(mview_cnt - batch_cnt)
        
        status = "✅" if diff == 0 else "⚠️"
        logger.info(f"{vx_type:<8} {mview_cnt:>10,} {batch_cnt:>10,} {diff:>8,} {status}")
        
        if diff > 0:
            all_consistent = False
    
    if all_consistent:
        logger.info("✅ Vx 歸屬邏輯一致")
    else:
        logger.warning("⚠️ Vx 歸屬邏輯不一致")
    
    return all_consistent


def test_v1_subtype(client):
    """測試 V1 子類型邏輯"""
    logger.info("=" * 60)
    logger.info("測試 V1 子類型邏輯")
    logger.info("=" * 60)
    
    # V1 子類型分布比較
    mview_v1 = client.query("""
        SELECT vx_subtype, count() as cnt 
        FROM silver.mv_fact_task_vx_attribution 
        WHERE vx_type = 'V1' AND vx_subtype IS NOT NULL
        GROUP BY vx_subtype 
        ORDER BY vx_subtype
    """)
    
    batch_v1 = client.query("""
        SELECT vx_subtype, count() as cnt 
        FROM silver.FACT_TASK_VX_ATTRIBUTION 
        WHERE vx_type = 'V1' AND vx_subtype IS NOT NULL
        GROUP BY vx_subtype 
        ORDER BY vx_subtype
    """)
    
    logger.info("V1 子類型分布比較:")
    logger.info("子類型     MVIEW筆數    批次筆數     差異")
    logger.info("-" * 50)
    
    mview_dict = {row[0]: row[1] for row in mview_v1.result_rows}
    batch_dict = {row[0]: row[1] for row in batch_v1.result_rows}
    
    all_subtypes = set(mview_dict.keys()) | set(batch_dict.keys())
    all_consistent = True
    
    for subtype in sorted(all_subtypes):
        mview_cnt = mview_dict.get(subtype, 0)
        batch_cnt = batch_dict.get(subtype, 0)
        diff = abs(mview_cnt - batch_cnt)
        
        status = "✅" if diff == 0 else "⚠️"
        logger.info(f"{subtype:<10} {mview_cnt:>10,} {batch_cnt:>10,} {diff:>8,} {status}")
        
        if diff > 0:
            all_consistent = False
    
    if all_consistent:
        logger.info("✅ V1 子類型邏輯一致")
    else:
        logger.warning("⚠️ V1 子類型邏輯不一致")
    
    return all_consistent


def test_exclusion_logic(client):
    """測試排除邏輯"""
    logger.info("=" * 60)
    logger.info("測試排除邏輯")
    logger.info("=" * 60)
    
    # 排除統計比較
    mview_exclusion = client.query("""
        SELECT 
            is_excluded,
            count() as cnt
        FROM silver.mv_fact_task_vx_attribution 
        GROUP BY is_excluded 
        ORDER BY is_excluded
    """)
    
    batch_exclusion = client.query("""
        SELECT 
            is_excluded,
            count() as cnt
        FROM silver.FACT_TASK_VX_ATTRIBUTION 
        GROUP BY is_excluded 
        ORDER BY is_excluded
    """)
    
    logger.info("排除邏輯比較:")
    logger.info("是否排除   MVIEW筆數    批次筆數     差異")
    logger.info("-" * 50)
    
    mview_dict = {row[0]: row[1] for row in mview_exclusion.result_rows}
    batch_dict = {row[0]: row[1] for row in batch_exclusion.result_rows}
    
    all_consistent = True
    
    for is_excluded in [0, 1]:
        mview_cnt = mview_dict.get(is_excluded, 0)
        batch_cnt = batch_dict.get(is_excluded, 0)
        diff = abs(mview_cnt - batch_cnt)
        
        status = "✅" if diff == 0 else "⚠️"
        excluded_text = "是" if is_excluded else "否"
        logger.info(f"{excluded_text:<8} {mview_cnt:>10,} {batch_cnt:>10,} {diff:>8,} {status}")
        
        if diff > 0:
            all_consistent = False
    
    if all_consistent:
        logger.info("✅ 排除邏輯一致")
    else:
        logger.warning("⚠️ 排除邏輯不一致")
    
    return all_consistent


def test_query_performance(client):
    """測試查詢效能"""
    logger.info("=" * 60)
    logger.info("測試查詢效能")
    logger.info("=" * 60)
    
    # 測試查詢 1: 簡單統計
    query1 = "SELECT count() FROM silver.mv_fact_task_vx_attribution WHERE task_create_date >= today() - 7"
    
    start_time = datetime.now()
    result1 = client.command(query1)
    mview_time1 = (datetime.now() - start_time).total_seconds()
    
    query1_batch = "SELECT count() FROM silver.FACT_TASK_VX_ATTRIBUTION WHERE task_create_date >= today() - 7"
    
    start_time = datetime.now()
    result1_batch = client.command(query1_batch)
    batch_time1 = (datetime.now() - start_time).total_seconds()
    
    logger.info(f"查詢 1 (近7日統計):")
    logger.info(f"  MVIEW: {mview_time1:.3f}秒, 結果: {result1:,}")
    logger.info(f"  批次表: {batch_time1:.3f}秒, 結果: {result1_batch:,}")
    logger.info(f"  效能提升: {((batch_time1 - mview_time1) / batch_time1 * 100):.1f}%")
    
    # 測試查詢 2: 複雜聚合
    query2 = """
        SELECT vx_type, task_status, count() 
        FROM silver.mv_fact_task_vx_attribution 
        WHERE is_excluded = 0 AND task_create_date >= today() - 30
        GROUP BY vx_type, task_status
    """
    
    start_time = datetime.now()
    result2 = client.query(query2)
    mview_time2 = (datetime.now() - start_time).total_seconds()
    
    query2_batch = """
        SELECT vx_type, task_status, count() 
        FROM silver.FACT_TASK_VX_ATTRIBUTION 
        WHERE is_excluded = 0 AND task_create_date >= today() - 30
        GROUP BY vx_type, task_status
    """
    
    start_time = datetime.now()
    result2_batch = client.query(query2_batch)
    batch_time2 = (datetime.now() - start_time).total_seconds()
    
    logger.info(f"查詢 2 (近30日聚合):")
    logger.info(f"  MVIEW: {mview_time2:.3f}秒, 結果: {len(result2.result_rows)}行")
    logger.info(f"  批次表: {batch_time2:.3f}秒, 結果: {len(result2_batch.result_rows)}行")
    logger.info(f"  效能提升: {((batch_time2 - mview_time2) / batch_time2 * 100):.1f}%")


def test_realtime_view(client):
    """測試即時查詢視圖"""
    logger.info("=" * 60)
    logger.info("測試即時查詢視圖")
    logger.info("=" * 60)
    
    try:
        # 測試視圖是否可用
        count = client.command("SELECT count() FROM silver.vw_fact_task_vx_attribution_realtime")
        logger.info(f"即時查詢視圖總筆數: {count:,}")
        
        # 測試視圖查詢效能
        start_time = datetime.now()
        result = client.query("""
            SELECT vx_type, count() 
            FROM silver.vw_fact_task_vx_attribution_realtime 
            WHERE task_create_date >= today() - 7
            GROUP BY vx_type
        """)
        query_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"即時視圖查詢耗時: {query_time:.3f}秒")
        logger.info("✅ 即時查詢視圖正常")
        return True
        
    except Exception as e:
        logger.error(f"❌ 即時查詢視圖錯誤: {e}")
        return False


def main():
    """主程式"""
    logger.info("=" * 80)
    logger.info("MVIEW 系統驗證開始")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    try:
        client = get_client()
        
        # 執行所有測試
        tests = [
            ("資料一致性", test_data_consistency),
            ("Vx 歸屬邏輯", test_vx_attribution),
            ("V1 子類型邏輯", test_v1_subtype),
            ("排除邏輯", test_exclusion_logic),
            ("即時查詢視圖", test_realtime_view),
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            try:
                results[test_name] = test_func(client)
            except Exception as e:
                logger.error(f"測試 {test_name} 失敗: {e}")
                results[test_name] = False
        
        # 效能測試（不影響整體結果）
        try:
            test_query_performance(client)
        except Exception as e:
            logger.error(f"效能測試失敗: {e}")
        
        # 總結
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info("=" * 80)
        logger.info("驗證結果總結")
        logger.info("=" * 80)
        
        passed = sum(results.values())
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ 通過" if result else "❌ 失敗"
            logger.info(f"{test_name:<20} {status}")
        
        logger.info("-" * 40)
        logger.info(f"總計: {passed}/{total} 項測試通過")
        logger.info(f"總耗時: {elapsed:.2f} 秒")
        
        if passed == total:
            logger.info("🎉 所有測試通過！MVIEW 系統運行正常")
            return True
        else:
            logger.warning(f"⚠️ {total - passed} 項測試失敗，請檢查 MVIEW 系統")
            return False
        
    except Exception as e:
        logger.error(f"驗證過程發生錯誤: {e}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)