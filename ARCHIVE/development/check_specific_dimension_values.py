#!/usr/bin/env python3
"""
檢查具體的維度值和交換邏輯
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 檢查具體的維度值和交換邏輯")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    try:
        # 1. 檢查 Silver 層的實際維度值分布
        print("📊 步驟 1：Silver 層維度值分布")
        dimension_dist_query = """
        SELECT 
            plant,
            factory,
            line,
            region_code,
            dimension_source,
            COUNT(*) as record_count
        FROM silver.mv_fact_task_vx_attribution_mdm
        WHERE task_create_date >= today() - INTERVAL 7 DAY
        GROUP BY plant, factory, line, region_code, dimension_source
        ORDER BY record_count DESC
        LIMIT 20
        """
        
        dist_result = client.query(dimension_dist_query)
        if dist_result.result_rows:
            print("✅ 維度值分布 (前20組合):")
            df_dist = pd.DataFrame(dist_result.result_rows, columns=dist_result.column_names)
            for _, row in df_dist.iterrows():
                print(f"   {row['region_code']}-{row['plant']}-{row['factory']}-{row['line']}: {row['record_count']} 筆 ({row['dimension_source']})")
        
        # 2. 檢查 VARINST 原始資料
        print(f"\n📊 步驟 2：VARINST 原始資料檢查")
        varinst_query = """
        SELECT 
            varinst_plant,
            varinst_factory,
            varinst_lineName,
            varinst_region,
            COUNT(*) as record_count
        FROM silver.mv_varinst_pivoted
        WHERE varinst_plant != '' OR varinst_factory != '' OR varinst_lineName != ''
        GROUP BY varinst_plant, varinst_factory, varinst_lineName, varinst_region
        ORDER BY record_count DESC
        LIMIT 20
        """
        
        varinst_result = client.query(varinst_query)
        if varinst_result.result_rows:
            print("✅ VARINST 原始值分布 (前20組合):")
            df_varinst = pd.DataFrame(varinst_result.result_rows, columns=varinst_result.column_names)
            for _, row in df_varinst.iterrows():
                print(f"   原始: {row['varinst_region']}-{row['varinst_plant']}-{row['varinst_factory']}-{row['varinst_lineName']}: {row['record_count']} 筆")
        
        # 3. 檢查 MDM 表的資料
        print(f"\n📊 步驟 3：MDM 表資料檢查")
        mdm_query = """
        SELECT 
            region_code,
            plant_code,
            factory_code,
            line_name,
            COUNT(*) as record_count
        FROM silver.dim_mfg_five_level
        WHERE line_name != ''
        GROUP BY region_code, plant_code, factory_code, line_name
        ORDER BY record_count DESC
        LIMIT 20
        """
        
        mdm_result = client.query(mdm_query)
        if mdm_result.result_rows:
            print("✅ MDM 維度值分布 (前20組合):")
            df_mdm = pd.DataFrame(mdm_result.result_rows, columns=mdm_result.column_names)
            for _, row in df_mdm.iterrows():
                print(f"   MDM: {row['region_code']}-{row['plant_code']}-{row['factory_code']}-{row['line_name']}: {row['record_count']} 筆")
        
        # 4. 檢查維度交換的具體案例
        print(f"\n📊 步驟 4：維度交換具體案例檢查")
        
        # 尋找包含 WJ2 和 NBU 的記錄
        specific_query = """
        SELECT 
            s.original_task_id,
            s.plant AS silver_plant,
            s.factory AS silver_factory,
            s.line AS silver_line,
            s.region_code AS silver_region,
            s.dimension_source,
            v.varinst_plant,
            v.varinst_factory,
            v.varinst_lineName,
            mdm.plant_code AS mdm_plant,
            mdm.factory_code AS mdm_factory,
            mdm.line_name AS mdm_line,
            mdm.region_code AS mdm_region
        FROM silver.mv_fact_task_vx_attribution_mdm AS s
        LEFT JOIN silver.mv_varinst_pivoted AS v ON s.proc_inst_id = v.PROC_INST_ID_
        LEFT JOIN silver.dim_mfg_five_level AS mdm ON v.varinst_lineName = mdm.line_name
        WHERE s.task_create_date >= today() - INTERVAL 30 DAY  -- 擴大範圍到30天
          AND (s.plant IN ('WJ2', 'NBU') OR s.factory IN ('WJ2', 'NBU')
               OR v.varinst_plant IN ('WJ2', 'NBU') OR v.varinst_factory IN ('WJ2', 'NBU'))
        LIMIT 10
        """
        
        specific_result = client.query(specific_query)
        if specific_result.result_rows:
            print("✅ 包含 WJ2/NBU 的具體案例:")
            df_specific = pd.DataFrame(specific_result.result_rows, columns=specific_result.column_names)
            for _, row in df_specific.iterrows():
                print(f"   Task: {row['original_task_id']}")
                print(f"   Silver: {row['silver_region']}-{row['silver_plant']}-{row['silver_factory']}-{row['silver_line']} ({row['dimension_source']})")
                if row['varinst_plant'] or row['varinst_factory']:
                    print(f"   VARINST: -{row['varinst_plant']}-{row['varinst_factory']}-{row['varinst_lineName']}")
                if row['mdm_plant'] or row['mdm_factory']:
                    print(f"   MDM: {row['mdm_region']}-{row['mdm_plant']}-{row['mdm_factory']}-{row['mdm_line']}")
                
                # 檢查維度交換
                if row['dimension_source'] == 'MDM_PRIMARY':
                    if (row['silver_plant'] == row['mdm_plant'] and 
                        row['silver_factory'] == row['mdm_factory']):
                        print(f"   ✅ MDM 映射正確")
                    else:
                        print(f"   ❌ MDM 映射異常")
                
                print()
        else:
            print("❌ 未找到包含 WJ2/NBU 的記錄")
        
        # 5. 檢查是否存在 VARINST 和 MDM 不一致的情況
        print(f"\n📊 步驟 5：VARINST vs MDM 一致性檢查")
        consistency_query = """
        WITH comparison AS (
            SELECT 
                v.varinst_plant,
                v.varinst_factory,
                v.varinst_lineName,
                mdm.plant_code AS mdm_plant,
                mdm.factory_code AS mdm_factory,
                mdm.line_name AS mdm_line,
                
                -- 檢查維度交換邏輯
                CASE 
                    WHEN v.varinst_plant = mdm.factory_code THEN 1 ELSE 0
                END AS plant_factory_swap_match,
                
                CASE 
                    WHEN v.varinst_factory = mdm.plant_code THEN 1 ELSE 0
                END AS factory_plant_swap_match,
                
                CASE 
                    WHEN v.varinst_lineName = mdm.line_name THEN 1 ELSE 0
                END AS line_match
                
            FROM silver.mv_varinst_pivoted AS v
            LEFT JOIN silver.dim_mfg_five_level AS mdm ON v.varinst_lineName = mdm.line_name
            WHERE v.varinst_plant != '' AND v.varinst_factory != '' AND v.varinst_lineName != ''
              AND mdm.line_name IS NOT NULL
            LIMIT 100
        )
        
        SELECT 
            COUNT(*) AS total_comparisons,
            SUM(plant_factory_swap_match) AS plant_factory_swaps,
            SUM(factory_plant_swap_match) AS factory_plant_swaps,
            SUM(line_match) AS line_matches,
            ROUND(SUM(plant_factory_swap_match) * 100.0 / COUNT(*), 2) AS plant_swap_rate,
            ROUND(SUM(factory_plant_swap_match) * 100.0 / COUNT(*), 2) AS factory_swap_rate,
            ROUND(SUM(line_match) * 100.0 / COUNT(*), 2) AS line_match_rate
        FROM comparison
        """
        
        consistency_result = client.query(consistency_query)
        if consistency_result.result_rows:
            consistency = consistency_result.result_rows[0]
            print("✅ VARINST vs MDM 一致性分析:")
            print(f"   總比較數: {consistency[0]}")
            print(f"   Plant-Factory 交換匹配: {consistency[1]} ({consistency[4]}%)")
            print(f"   Factory-Plant 交換匹配: {consistency[2]} ({consistency[5]}%)")
            print(f"   Line 直接匹配: {consistency[3]} ({consistency[6]}%)")
        
        return True
        
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        client.close()

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\n✅ 檢查完成")
    else:
        print("\n❌ 檢查失敗")