#!/usr/bin/env python3
"""
MDM 製造五階維度資料品質檢核腳本
檢核 silver.dim_mfg_five_level 維度表的資料品質
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

def check_dimension_completeness(client):
    """檢核維度完整性"""
    print("=" * 80)
    print("📊 維度完整性檢核")
    print("=" * 80)
    
    # 總體統計
    result = client.query("""
    SELECT 
        count() as total_lines,
        sum(is_valid) as valid_lines,
        round(sum(is_valid) * 100.0 / count(), 2) as valid_percentage,
        count(DISTINCT region_code) as unique_regions,
        count(DISTINCT plant_code) as unique_plants,
        count(DISTINCT factory_code) as unique_factories
    FROM silver.dim_mfg_five_level
    """)
    
    if result.result_rows:
        total, valid, pct, regions, plants, factories = result.result_rows[0]
        print(f"總線數: {total:,}")
        print(f"有效線數: {valid:,} ({pct}%)")
        print(f"唯一 Region: {regions}")
        print(f"唯一 Plant: {plants}")
        print(f"唯一 Factory: {factories}")
    
    # 缺失原因分布
    print(f"\n📋 缺失原因分布:")
    result = client.query("""
    SELECT 
        COALESCE(missing_reason, 'COMPLETE') as reason,
        count() as line_count,
        round(count() * 100.0 / (SELECT count() FROM silver.dim_mfg_five_level), 2) as percentage
    FROM silver.dim_mfg_five_level
    GROUP BY missing_reason
    ORDER BY line_count DESC
    """)
    
    for row in result.result_rows:
        reason, count, pct = row
        print(f"  {reason:<30} {count:>6,} 條線 ({pct:>5.1f}%)")

def check_orphan_rates(client):
    """檢核各層 orphan rate"""
    print(f"\n📊 各層 Orphan Rate 檢核")
    print("-" * 80)
    
    result = client.query("""
    WITH orphan_stats AS (
        SELECT 
            count() as total_lines,
            sum(CASE WHEN prod_area_id IS NULL THEN 1 ELSE 0 END) as line_orphan,
            sum(CASE WHEN factory_code IS NULL THEN 1 ELSE 0 END) as factory_orphan,
            sum(CASE WHEN plant_code IS NULL THEN 1 ELSE 0 END) as plant_orphan,
            sum(CASE WHEN region_code IS NULL THEN 1 ELSE 0 END) as region_orphan
        FROM silver.dim_mfg_five_level
    )
    SELECT 
        'Line → PROD_AREA' as level,
        line_orphan as orphan_count,
        round(line_orphan * 100.0 / total_lines, 2) as orphan_rate
    FROM orphan_stats
    
    UNION ALL
    
    SELECT 
        'PROD_AREA → Factory' as level,
        factory_orphan as orphan_count,
        round(factory_orphan * 100.0 / total_lines, 2) as orphan_rate
    FROM orphan_stats
    
    UNION ALL
    
    SELECT 
        'Factory → Plant' as level,
        plant_orphan as orphan_count,
        round(plant_orphan * 100.0 / total_lines, 2) as orphan_rate
    FROM orphan_stats
    
    UNION ALL
    
    SELECT 
        'Factory → Region' as level,
        region_orphan as orphan_count,
        round(region_orphan * 100.0 / total_lines, 2) as orphan_rate
    FROM orphan_stats
    """)
    
    for row in result.result_rows:
        level, count, rate = row
        status = "✅" if rate < 10 else "⚠️" if rate < 20 else "❌"
        print(f"{status} {level:<20} {count:>6,} 條線 ({rate:>5.1f}%)")

def check_disambiguation_needed(client):
    """檢核需要 disambiguation 的情況"""
    print(f"\n🔍 Disambiguation 檢核")
    print("-" * 80)
    
    # 同一 line_name 對應多個 factory_code
    result = client.query("""
    SELECT 
        line_name,
        count(DISTINCT factory_code) as factory_count,
        groupArray(DISTINCT factory_code) as factory_codes
    FROM silver.dim_mfg_five_level
    WHERE factory_code IS NOT NULL
    GROUP BY line_name
    HAVING factory_count > 1
    ORDER BY factory_count DESC
    LIMIT 10
    """)
    
    if result.result_rows:
        print("⚠️ 同一 LINE 對應多個 FACTORY (需要 disambiguation):")
        for row in result.result_rows:
            line_name, factory_count, factory_codes = row
            print(f"  {line_name}: {factory_count} 個 Factory {factory_codes}")
    else:
        print("✅ 無 LINE → FACTORY disambiguation 問題")
    
    # 同一 factory_code 對應多個 plant_code
    result = client.query("""
    SELECT 
        factory_code,
        count(DISTINCT plant_code) as plant_count,
        groupArray(DISTINCT plant_code) as plant_codes
    FROM silver.dim_mfg_five_level
    WHERE factory_code IS NOT NULL AND plant_code IS NOT NULL
    GROUP BY factory_code
    HAVING plant_count > 1
    ORDER BY plant_count DESC
    LIMIT 10
    """)
    
    if result.result_rows:
        print("\n⚠️ 同一 FACTORY 對應多個 PLANT (需要 disambiguation):")
        for row in result.result_rows:
            factory_code, plant_count, plant_codes = row
            print(f"  {factory_code}: {plant_count} 個 Plant {plant_codes}")
    else:
        print("\n✅ 無 FACTORY → PLANT disambiguation 問題")

def check_flowable_coverage(client):
    """檢核 Flowable 任務的 MDM 覆蓋率"""
    print(f"\n📈 Flowable 任務 MDM 覆蓋率檢核")
    print("-" * 80)
    
    # 檢查 Flowable 任務能否 JOIN 到 MDM 維度表
    result = client.query("""
    WITH flowable_lines AS (
        SELECT DISTINCT Line as line_name
        FROM bronze.common_flowable_task_stats
        WHERE Line IS NOT NULL AND Line != ''
    ),
    coverage_stats AS (
        SELECT 
            count() as total_flowable_lines,
            sum(CASE WHEN dim.line_name IS NOT NULL THEN 1 ELSE 0 END) as covered_lines
        FROM flowable_lines f
        LEFT JOIN silver.dim_mfg_five_level dim ON f.line_name = dim.line_name
    )
    SELECT 
        total_flowable_lines,
        covered_lines,
        round(covered_lines * 100.0 / total_flowable_lines, 2) as coverage_rate
    FROM coverage_stats
    """)
    
    if result.result_rows:
        total, covered, rate = result.result_rows[0]
        status = "✅" if rate >= 80 else "⚠️" if rate >= 60 else "❌"
        print(f"{status} Flowable Line 覆蓋率: {covered:,}/{total:,} ({rate}%)")
    
    # 檢查未覆蓋的 Top 10 Line
    result = client.query("""
    WITH flowable_lines AS (
        SELECT Line as line_name, count() as task_count
        FROM bronze.common_flowable_task_stats
        WHERE Line IS NOT NULL AND Line != ''
        GROUP BY Line
    )
    SELECT 
        f.line_name,
        f.task_count
    FROM flowable_lines f
    LEFT JOIN silver.dim_mfg_five_level dim ON f.line_name = dim.line_name
    WHERE dim.line_name IS NULL
    ORDER BY f.task_count DESC
    LIMIT 10
    """)
    
    if result.result_rows:
        print(f"\n❌ 未覆蓋的 Top 10 Line (需要 Flowable fallback):")
        for row in result.result_rows:
            line_name, task_count = row
            print(f"  {line_name}: {task_count:,} 個任務")
    else:
        print(f"\n✅ 所有 Flowable Line 都已覆蓋")

def check_data_freshness(client):
    """檢核資料新鮮度"""
    print(f"\n🕒 資料新鮮度檢核")
    print("-" * 80)
    
    result = client.query("""
    SELECT 
        min(_create_time) as earliest_create,
        max(_create_time) as latest_create,
        min(_update_time) as earliest_update,
        max(_update_time) as latest_update
    FROM silver.dim_mfg_five_level
    """)
    
    if result.result_rows:
        earliest_create, latest_create, earliest_update, latest_update = result.result_rows[0]
        print(f"建立時間範圍: {earliest_create} ~ {latest_create}")
        print(f"更新時間範圍: {earliest_update} ~ {latest_update}")

def generate_quality_summary(client):
    """產生品質總結報告"""
    print(f"\n📋 資料品質總結報告")
    print("=" * 80)
    
    # 計算各項品質指標
    result = client.query("""
    WITH quality_metrics AS (
        SELECT 
            count() as total_lines,
            sum(is_valid) as valid_lines,
            sum(CASE WHEN prod_area_id IS NULL THEN 1 ELSE 0 END) as line_orphan,
            sum(CASE WHEN factory_code IS NULL THEN 1 ELSE 0 END) as factory_orphan,
            sum(CASE WHEN plant_code IS NULL THEN 1 ELSE 0 END) as plant_orphan,
            sum(CASE WHEN region_code IS NULL THEN 1 ELSE 0 END) as region_orphan
        FROM silver.dim_mfg_five_level
    )
    SELECT 
        round(valid_lines * 100.0 / total_lines, 2) as completeness_rate,
        round(line_orphan * 100.0 / total_lines, 2) as line_orphan_rate,
        round(factory_orphan * 100.0 / total_lines, 2) as factory_orphan_rate,
        round(plant_orphan * 100.0 / total_lines, 2) as plant_orphan_rate,
        round(region_orphan * 100.0 / total_lines, 2) as region_orphan_rate
    FROM quality_metrics
    """)
    
    if result.result_rows:
        completeness, line_orphan, factory_orphan, plant_orphan, region_orphan = result.result_rows[0]
        
        print(f"✅ 維度完整性: {completeness}% (目標: >80%)")
        print(f"{'✅' if line_orphan < 10 else '⚠️'} Line Orphan Rate: {line_orphan}% (目標: <10%)")
        print(f"{'✅' if factory_orphan < 5 else '⚠️'} Factory Orphan Rate: {factory_orphan}% (目標: <5%)")
        print(f"{'✅' if plant_orphan < 5 else '⚠️'} Plant Orphan Rate: {plant_orphan}% (目標: <5%)")
        print(f"{'✅' if region_orphan < 5 else '⚠️'} Region Orphan Rate: {region_orphan}% (目標: <5%)")
        
        # 總體評分
        score = 0
        if completeness >= 80: score += 20
        if line_orphan < 10: score += 20
        if factory_orphan < 5: score += 20
        if plant_orphan < 5: score += 20
        if region_orphan < 5: score += 20
        
        print(f"\n🎯 總體品質評分: {score}/100")
        if score >= 80:
            print("✅ 資料品質良好，可以投入生產使用")
        elif score >= 60:
            print("⚠️ 資料品質尚可，建議優化後使用")
        else:
            print("❌ 資料品質不佳，需要修正後才能使用")

def main():
    """主程式"""
    logger.info("開始 MDM 製造五階維度資料品質檢核")
    
    try:
        client = get_client()
        
        # 執行各項檢核
        check_dimension_completeness(client)
        check_orphan_rates(client)
        check_disambiguation_needed(client)
        check_flowable_coverage(client)
        check_data_freshness(client)
        generate_quality_summary(client)
        
        logger.info("資料品質檢核完成")
        
    except Exception as e:
        logger.error(f"檢核失敗: {e}")
        raise

if __name__ == "__main__":
    main()