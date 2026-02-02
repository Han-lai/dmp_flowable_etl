#!/usr/bin/env python3
"""
備份並更新 silver.mv_fact_task_vx_attribution_mdm
實作完整的維度補齊邏輯
"""

import clickhouse_connect
import pandas as pd
from datetime import datetime

def main():
    print("🔄 更新 Silver Layer MView - 維度補齊邏輯")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 步驟 1: 檢查現有表結構
        print("📊 步驟 1: 檢查現有表結構")
        print("-" * 50)
        
        desc_result = client.query("DESCRIBE silver.mv_fact_task_vx_attribution_mdm")
        current_columns = [row[0] for row in desc_result.result_rows]
        
        print("✅ 現有欄位:")
        for col in current_columns:
            print(f"   {col}")
        
        # 檢查是否已有資料來源追蹤欄位
        source_columns = [col for col in current_columns if '_source' in col]
        print(f"\n📋 現有資料來源欄位: {source_columns}")
        
        # 步驟 2: 檢查資料量
        print(f"\n📊 步驟 2: 檢查資料量")
        print("-" * 50)
        
        count_result = client.query("SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution_mdm")
        total_rows = count_result.result_rows[0][0]
        print(f"✅ 總記錄數: {total_rows:,}")
        
        # 檢查最近資料
        recent_result = client.query("""
        SELECT 
            MIN(task_create_date) as min_date,
            MAX(task_create_date) as max_date,
            COUNT(DISTINCT task_create_date) as date_count
        FROM silver.mv_fact_task_vx_attribution_mdm
        """)
        
        if recent_result.result_rows:
            min_date, max_date, date_count = recent_result.result_rows[0]
            print(f"✅ 資料範圍: {min_date} ~ {max_date} ({date_count} 天)")
        
        # 步驟 3: 檢查維度完整性
        print(f"\n📊 步驟 3: 檢查維度完整性")
        print("-" * 50)
        
        dimension_check = client.query("""
        SELECT 
            COUNT(*) as total_records,
            SUM(CASE WHEN region_code IS NOT NULL AND region_code != '' THEN 1 ELSE 0 END) as has_region,
            SUM(CASE WHEN plant_code IS NOT NULL AND plant_code != '' THEN 1 ELSE 0 END) as has_plant,
            SUM(CASE WHEN factory_code IS NOT NULL AND factory_code != '' THEN 1 ELSE 0 END) as has_factory,
            SUM(CASE WHEN line_name IS NOT NULL AND line_name != '' THEN 1 ELSE 0 END) as has_line
        FROM silver.mv_fact_task_vx_attribution_mdm
        WHERE task_create_date >= '2025-12-01'
        """)
        
        if dimension_check.result_rows:
            total, has_region, has_plant, has_factory, has_line = dimension_check.result_rows[0]
            
            print(f"✅ 維度完整性 (近期資料):")
            print(f"   總記錄: {total:,}")
            print(f"   Region: {has_region:,} ({has_region/total*100:.1f}%)")
            print(f"   Plant: {has_plant:,} ({has_plant/total*100:.1f}%)")
            print(f"   Factory: {has_factory:,} ({has_factory/total*100:.1f}%)")
            print(f"   Line: {has_line:,} ({has_line/total*100:.1f}%)")
        
        # 步驟 4: 檢查 dimension_source 分布
        print(f"\n📊 步驟 4: 檢查 dimension_source 分布")
        print("-" * 50)
        
        source_dist = client.query("""
        SELECT 
            dimension_source,
            COUNT(*) as record_count,
            COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() as percentage
        FROM silver.mv_fact_task_vx_attribution_mdm
        WHERE task_create_date >= '2025-12-01'
        GROUP BY dimension_source
        ORDER BY record_count DESC
        """)
        
        if source_dist.result_rows:
            print("✅ 資料來源分布:")
            for source, count, pct in source_dist.result_rows:
                print(f"   {source}: {count:,} ({pct:.1f}%)")
        
        # 步驟 5: 確認是否需要更新
        print(f"\n📊 步驟 5: 確認更新需求")
        print("-" * 50)
        
        needs_update = False
        update_reasons = []
        
        # 檢查是否有個別維度的資料來源欄位
        required_source_cols = ['region_source', 'plant_source', 'factory_source', 'line_source']
        missing_source_cols = [col for col in required_source_cols if col not in current_columns]
        
        if missing_source_cols:
            needs_update = True
            update_reasons.append(f"缺少資料來源欄位: {', '.join(missing_source_cols)}")
        
        # 檢查是否有 region 欄位 (非 region_code)
        if 'region' not in current_columns:
            needs_update = True
            update_reasons.append("缺少 region 欄位 (目前只有 region_code)")
        
        if needs_update:
            print("⚠️ 需要更新:")
            for reason in update_reasons:
                print(f"   - {reason}")
            
            return True, {
                'total_rows': total_rows,
                'current_columns': current_columns,
                'missing_source_cols': missing_source_cols
            }
        else:
            print("✅ 表結構已符合要求，無需更新")
            return False, None
        
    except Exception as e:
        print(f"❌ 檢查失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None
    
    finally:
        client.close()

if __name__ == "__main__":
    needs_update, info = main()
    if needs_update:
        print(f"\n🔄 準備進行更新...")
    else:
        print(f"\n✅ 檢查完成")