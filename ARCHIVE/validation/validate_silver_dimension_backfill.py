#!/usr/bin/env python3
"""
驗證 Silver 層維度補齊邏輯
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 驗證 Silver 層維度補齊邏輯")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 1. 檢查維度來源分布
        print("📊 步驟 1: 檢查維度來源分布")
        print("-" * 50)
        
        source_dist_query = """
        SELECT 
            region_source,
            plant_source,
            factory_source,
            line_source,
            COUNT(*) as record_count
        FROM silver.mv_fact_task_vx_attribution_mdm
        WHERE task_create_date >= '2025-12-01'
        GROUP BY region_source, plant_source, factory_source, line_source
        ORDER BY record_count DESC
        LIMIT 10
        """
        
        source_result = client.query(source_dist_query)
        if source_result.result_rows:
            print("✅ 維度來源分布:")
            for region_src, plant_src, factory_src, line_src, count in source_result.result_rows:
                print(f"   R:{region_src}, P:{plant_src}, F:{factory_src}, L:{line_src} - {count:,} records")
        
        # 2. 檢查 MDM 補齊效果
        print(f"\n📊 步驟 2: 檢查 MDM 補齊效果")
        print("-" * 50)
        
        backfill_stats_query = """
        SELECT 
            COUNT(*) as total_records,
            
            -- Region 補齊統計
            SUM(CASE WHEN region != '' THEN 1 ELSE 0 END) as has_region,
            SUM(CASE WHEN region_source = 'VARINST' THEN 1 ELSE 0 END) as region_from_varinst,
            SUM(CASE WHEN region_source = 'MDM' THEN 1 ELSE 0 END) as region_from_mdm,
            
            -- Plant 補齊統計
            SUM(CASE WHEN plant != '' THEN 1 ELSE 0 END) as has_plant,
            SUM(CASE WHEN plant_source = 'VARINST' THEN 1 ELSE 0 END) as plant_from_varinst,
            SUM(CASE WHEN plant_source = 'MDM' THEN 1 ELSE 0 END) as plant_from_mdm,
            
            -- Factory 補齊統計
            SUM(CASE WHEN factory != '' THEN 1 ELSE 0 END) as has_factory,
            SUM(CASE WHEN factory_source = 'VARINST' THEN 1 ELSE 0 END) as factory_from_varinst,
            SUM(CASE WHEN factory_source = 'MDM' THEN 1 ELSE 0 END) as factory_from_mdm,
            
            -- Line 補齊統計
            SUM(CASE WHEN line != '' THEN 1 ELSE 0 END) as has_line,
            SUM(CASE WHEN line_source = 'VARINST' THEN 1 ELSE 0 END) as line_from_varinst,
            SUM(CASE WHEN line_source = 'MDM' THEN 1 ELSE 0 END) as line_from_mdm
            
        FROM silver.mv_fact_task_vx_attribution_mdm
        WHERE task_create_date >= '2025-12-01'
        """
        
        stats_result = client.query(backfill_stats_query)
        if stats_result.result_rows:
            stats = stats_result.result_rows[0]
            total = stats[0]
            
            print(f"✅ 補齊效果統計 (近期資料，總計 {total:,} 筆):")
            print(f"   Region: {stats[1]:,} ({stats[1]/total*100:.1f}%) - VARINST: {stats[2]:,}, MDM: {stats[3]:,}")
            print(f"   Plant:  {stats[4]:,} ({stats[4]/total*100:.1f}%) - VARINST: {stats[5]:,}, MDM: {stats[6]:,}")
            print(f"   Factory:{stats[7]:,} ({stats[7]/total*100:.1f}%) - VARINST: {stats[8]:,}, MDM: {stats[9]:,}")
            print(f"   Line:   {stats[10]:,} ({stats[10]/total*100:.1f}%) - VARINST: {stats[11]:,}, MDM: {stats[12]:,}")
        
        # 3. 驗證 VARINST 優先原則
        print(f"\n📊 步驟 3: 驗證 VARINST 優先原則")
        print("-" * 50)
        
        # 使用測試樣本驗證
        test_samples = [
            '38cfc17e-ef5a-11f0-a787-0a5a5063cfa7',  # 已知的測試樣本
        ]
        
        for proc_id in test_samples:
            sample_query = f"""
            SELECT 
                proc_inst_id,
                region, region_source,
                plant, plant_source,
                factory, factory_source,
                line, line_source
            FROM silver.mv_fact_task_vx_attribution_mdm
            WHERE proc_inst_id = '{proc_id}'
            LIMIT 1
            """
            
            sample_result = client.query(sample_query)
            if sample_result.result_rows:
                row = sample_result.result_rows[0]
                print(f"✅ 測試樣本 {proc_id[-12:]}:")
                print(f"   Region: '{row[1]}' (來源: {row[2]})")
                print(f"   Plant:  '{row[3]}' (來源: {row[4]})")
                print(f"   Factory:'{row[5]}' (來源: {row[6]})")
                print(f"   Line:   '{row[7]}' (來源: {row[8]})")
        
        # 4. 檢查資料品質
        print(f"\n📊 步驟 4: 檢查資料品質")
        print("-" * 50)
        
        quality_query = """
        SELECT 
            dimension_source,
            COUNT(*) as record_count,
            COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() as percentage
        FROM silver.mv_fact_task_vx_attribution_mdm
        WHERE task_create_date >= '2025-12-01'
        GROUP BY dimension_source
        ORDER BY record_count DESC
        """
        
        quality_result = client.query(quality_query)
        if quality_result.result_rows:
            print("✅ 整體維度來源分布:")
            for source, count, pct in quality_result.result_rows:
                print(f"   {source}: {count:,} ({pct:.1f}%)")
        
        return True
        
    except Exception as e:
        print(f"❌ 驗證失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        client.close()

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\n✅ Silver 層維度補齊邏輯驗證完成")
    else:
        print(f"\n❌ 驗證失敗")