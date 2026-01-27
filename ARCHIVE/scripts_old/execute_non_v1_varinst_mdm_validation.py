#!/usr/bin/env python3
"""
執行非 V1 流程 VARINST vs MDM 缺口分析驗證
"""

import clickhouse_connect
import pandas as pd

def main():
    print("🔍 執行非 V1 流程 VARINST vs MDM 缺口分析驗證")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    target_proc_inst_ids = [
        '3c40f619-c593-11f0-8d58-1e564a6128f7',
        '38cfc17e-ef5a-11f0-a787-0a5a5063cfa7', 
        '3ca530c5-d938-11f0-8eb2-761d901080ab',
        '505b457d-63b3-11f0-b8b8-b6733f7db4dd',
        '3c60482b-ecf9-11f0-ba59-92564f99f227',
        '3ca93700-ef50-11f0-a787-0a5a5063cfa7'
    ]
    
    try:
        # 1. VARINST 實際內容檢查
        print("📊 步驟 1：VARINST 實際內容檢查")
        
        varinst_content_query = f"""
        SELECT 
            PROC_INST_ID_,
            NAME_,
            TEXT_,
            CASE WHEN TEXT_ IS NULL OR TEXT_ = '' THEN '❌ 空值' ELSE '✅ 有值' END AS has_value
        FROM bronze.bpm_act_hi_varinst
        WHERE PROC_INST_ID_ IN ({','.join([f"'{pid}'" for pid in target_proc_inst_ids])})
          AND NAME_ IS NOT NULL AND NAME_ != ''
        ORDER BY PROC_INST_ID_, NAME_
        """
        
        varinst_content_result = client.query(varinst_content_query)
        if varinst_content_result.result_rows:
            print("✅ VARINST 實際內容:")
            df_varinst = pd.DataFrame(varinst_content_result.result_rows, columns=varinst_content_result.column_names)
            
            # 按 PROC_INST_ID_ 分組顯示
            for proc_id in target_proc_inst_ids:
                proc_data = df_varinst[df_varinst['PROC_INST_ID_'] == proc_id]
                print(f"\n   🔍 {proc_id}:")
                if len(proc_data) > 0:
                    for _, row in proc_data.iterrows():
                        print(f"      {row['NAME_']}: {row['TEXT_']} ({row['has_value']})")
                else:
                    print(f"      ❌ 無任何 VARINST 記錄")
        else:
            print("❌ 無 VARINST 資料")
        
        # 2. 維度缺失彙總
        print(f"\n📊 步驟 2：維度缺失彙總")
        
        dimension_missing_query = f"""
        WITH target_proc_inst AS (
            SELECT arrayJoin([{','.join([f"'{pid}'" for pid in target_proc_inst_ids])}]) AS proc_inst_id
        )
        
        SELECT 
            t.proc_inst_id,
            
            CASE 
                WHEN v_region.PROC_INST_ID_ IS NOT NULL THEN '✅ 存在' 
                ELSE '❌ 缺失' 
            END AS region_status,
            
            CASE 
                WHEN v_plant.PROC_INST_ID_ IS NOT NULL THEN '✅ 存在' 
                ELSE '❌ 缺失' 
            END AS plant_status,
            
            CASE 
                WHEN v_factory.PROC_INST_ID_ IS NOT NULL THEN '✅ 存在' 
                ELSE '❌ 缺失' 
            END AS factory_status,
            
            CASE 
                WHEN v_line.PROC_INST_ID_ IS NOT NULL THEN '✅ 存在' 
                ELSE '❌ 缺失' 
            END AS lineName_status,
            
            CASE WHEN v_region.PROC_INST_ID_ IS NULL THEN 1 ELSE 0 END +
            CASE WHEN v_plant.PROC_INST_ID_ IS NULL THEN 1 ELSE 0 END +
            CASE WHEN v_factory.PROC_INST_ID_ IS NULL THEN 1 ELSE 0 END +
            CASE WHEN v_line.PROC_INST_ID_ IS NULL THEN 1 ELSE 0 END AS missing_count
            
        FROM target_proc_inst AS t
        LEFT JOIN (
            SELECT DISTINCT PROC_INST_ID_ 
            FROM bronze.bpm_act_hi_varinst 
            WHERE NAME_ = 'region' AND TEXT_ IS NOT NULL AND TEXT_ != ''
        ) AS v_region ON t.proc_inst_id = v_region.PROC_INST_ID_
        LEFT JOIN (
            SELECT DISTINCT PROC_INST_ID_ 
            FROM bronze.bpm_act_hi_varinst 
            WHERE NAME_ = 'plant' AND TEXT_ IS NOT NULL AND TEXT_ != ''
        ) AS v_plant ON t.proc_inst_id = v_plant.PROC_INST_ID_
        LEFT JOIN (
            SELECT DISTINCT PROC_INST_ID_ 
            FROM bronze.bpm_act_hi_varinst 
            WHERE NAME_ = 'factory' AND TEXT_ IS NOT NULL AND TEXT_ != ''
        ) AS v_factory ON t.proc_inst_id = v_factory.PROC_INST_ID_
        LEFT JOIN (
            SELECT DISTINCT PROC_INST_ID_ 
            FROM bronze.bpm_act_hi_varinst 
            WHERE NAME_ = 'lineName' AND TEXT_ IS NOT NULL AND TEXT_ != ''
        ) AS v_line ON t.proc_inst_id = v_line.PROC_INST_ID_
        
        ORDER BY t.proc_inst_id
        """
        
        dimension_result = client.query(dimension_missing_query)
        if dimension_result.result_rows:
            print("✅ 維度缺失彙總:")
            df_dimension = pd.DataFrame(dimension_result.result_rows, columns=dimension_result.column_names)
            for _, row in df_dimension.iterrows():
                print(f"   {row['proc_inst_id']}:")
                print(f"      Region: {row['region_status']}")
                print(f"      Plant: {row['plant_status']}")
                print(f"      Factory: {row['factory_status']}")
                print(f"      LineName: {row['lineName_status']}")
                print(f"      缺失維度數: {row['missing_count']}/4")
                print()
        
        # 3. MDM 補齊驗證
        print(f"📊 步驟 3：MDM 補齊驗證")
        
        mdm_补齐_query = f"""
        WITH target_proc_inst AS (
            SELECT arrayJoin([{','.join([f"'{pid}'" for pid in target_proc_inst_ids])}]) AS proc_inst_id
        ),
        proc_with_keys AS (
            SELECT 
                p.PROC_INST_ID_,
                p.BUSINESS_KEY_,
                
                multiIf(
                    p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
                    extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'),
                    ''
                ) AS business_key_line
                
            FROM bronze.bpm_act_hi_procinst AS p
            INNER JOIN target_proc_inst AS t ON p.PROC_INST_ID_ = t.proc_inst_id
        ),
        mdm_mapping AS (
            SELECT 
                pk.PROC_INST_ID_,
                pk.business_key_line,
                
                mdm.region_code AS mdm_region,
                mdm.plant_code AS mdm_plant,
                mdm.factory_code AS mdm_factory,
                mdm.line_name AS mdm_line,
                
                CASE 
                    WHEN mdm.line_name IS NOT NULL THEN '✅ MDM 成功'
                    ELSE '❌ MDM 失敗'
                END AS mdm_join_status
                
            FROM proc_with_keys AS pk
            LEFT JOIN silver.dim_mfg_five_level AS mdm ON pk.business_key_line = mdm.line_name
        )
        
        SELECT 
            PROC_INST_ID_,
            business_key_line,
            mdm_join_status,
            mdm_region,
            mdm_plant,
            mdm_factory,
            mdm_line
        FROM mdm_mapping
        ORDER BY PROC_INST_ID_
        """
        
        mdm_result = client.query(mdm_补齐_query)
        if mdm_result.result_rows:
            print("✅ MDM 補齊結果:")
            df_mdm = pd.DataFrame(mdm_result.result_rows, columns=mdm_result.column_names)
            for _, row in df_mdm.iterrows():
                print(f"   {row['PROC_INST_ID_']}:")
                print(f"      Join Key: {row['business_key_line']}")
                print(f"      MDM Status: {row['mdm_join_status']}")
                if row['mdm_join_status'] == '✅ MDM 成功':
                    print(f"      Region: {row['mdm_region']}")
                    print(f"      Plant: {row['mdm_plant']}")
                    print(f"      Factory: {row['mdm_factory']}")
                    print(f"      Line: {row['mdm_line']}")
                print()
        
        # 4. VARINST vs MDM 對照
        print(f"📊 步驟 4：VARINST vs MDM 對照")
        
        comparison_query = f"""
        WITH target_proc_inst AS (
            SELECT arrayJoin([{','.join([f"'{pid}'" for pid in target_proc_inst_ids])}]) AS proc_inst_id
        ),
        varinst_dimensions AS (
            SELECT 
                t.proc_inst_id,
                v_region.TEXT_ AS varinst_region,
                v_plant.TEXT_ AS varinst_plant,
                v_factory.TEXT_ AS varinst_factory,
                v_line.TEXT_ AS varinst_line
                 
            FROM target_proc_inst AS t
            LEFT JOIN (
                SELECT PROC_INST_ID_, TEXT_ 
                FROM bronze.bpm_act_hi_varinst 
                WHERE NAME_ = 'region' AND TEXT_ IS NOT NULL AND TEXT_ != ''
            ) AS v_region ON t.proc_inst_id = v_region.PROC_INST_ID_
            LEFT JOIN (
                SELECT PROC_INST_ID_, TEXT_ 
                FROM bronze.bpm_act_hi_varinst 
                WHERE NAME_ = 'plant' AND TEXT_ IS NOT NULL AND TEXT_ != ''
            ) AS v_plant ON t.proc_inst_id = v_plant.PROC_INST_ID_
            LEFT JOIN (
                SELECT PROC_INST_ID_, TEXT_ 
                FROM bronze.bpm_act_hi_varinst 
                WHERE NAME_ = 'factory' AND TEXT_ IS NOT NULL AND TEXT_ != ''
            ) AS v_factory ON t.proc_inst_id = v_factory.PROC_INST_ID_
            LEFT JOIN (
                SELECT PROC_INST_ID_, TEXT_ 
                FROM bronze.bpm_act_hi_varinst 
                WHERE NAME_ = 'lineName' AND TEXT_ IS NOT NULL AND TEXT_ != ''
            ) AS v_line ON t.proc_inst_id = v_line.PROC_INST_ID_
        ),
        mdm_dimensions AS (
            SELECT 
                p.PROC_INST_ID_,
                
                multiIf(
                    p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
                    extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'),
                    ''
                ) AS join_key,
                
                mdm.region_code AS mdm_region,
                mdm.plant_code AS mdm_plant,
                mdm.factory_code AS mdm_factory,
                mdm.line_name AS mdm_line
                
            FROM bronze.bpm_act_hi_procinst AS p
            INNER JOIN target_proc_inst AS t ON p.PROC_INST_ID_ = t.proc_inst_id
            LEFT JOIN silver.dim_mfg_five_level AS mdm ON 
                multiIf(
                    p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
                    extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'),
                    ''
                ) = mdm.line_name
        )
        
        SELECT 
            v.proc_inst_id,
            
            COALESCE(v.varinst_region, 'NULL') AS varinst_region,
            COALESCE(v.varinst_plant, 'NULL') AS varinst_plant,
            COALESCE(v.varinst_factory, 'NULL') AS varinst_factory,
            COALESCE(v.varinst_line, 'NULL') AS varinst_line,
            
            COALESCE(m.mdm_region, 'NULL') AS mdm_region,
            COALESCE(m.mdm_plant, 'NULL') AS mdm_plant,
            COALESCE(m.mdm_factory, 'NULL') AS mdm_factory,
            COALESCE(m.mdm_line, 'NULL') AS mdm_line
            
        FROM varinst_dimensions AS v
        LEFT JOIN mdm_dimensions AS m ON v.proc_inst_id = m.PROC_INST_ID_
        ORDER BY v.proc_inst_id
        """
        
        comparison_result = client.query(comparison_query)
        if comparison_result.result_rows:
            print("✅ VARINST vs MDM 對照表:")
            df_comparison = pd.DataFrame(comparison_result.result_rows, columns=comparison_result.column_names)
            
            print(f"{'PROC_INST_ID':<40} {'VARINST':<25} {'MDM':<25} {'補齊狀況'}")
            print("-" * 100)
            
            for _, row in df_comparison.iterrows():
                varinst_dims = f"{row['varinst_region']}-{row['varinst_plant']}-{row['varinst_factory']}-{row['varinst_line']}"
                mdm_dims = f"{row['mdm_region']}-{row['mdm_plant']}-{row['mdm_factory']}-{row['mdm_line']}"
                
                # 計算補齊狀況
                varinst_nulls = sum(1 for v in [row['varinst_region'], row['varinst_plant'], row['varinst_factory'], row['varinst_line']] if v == 'NULL')
                mdm_values = sum(1 for v in [row['mdm_region'], row['mdm_plant'], row['mdm_factory'], row['mdm_line']] if v != 'NULL')
                
                if varinst_nulls > 0 and mdm_values > 0:
                    status = f"✅ MDM補齊{mdm_values}個"
                elif varinst_nulls == 4 and mdm_values == 0:
                    status = "❌ 都無值"
                elif varinst_nulls == 0:
                    status = "⚠️ VARINST完整"
                else:
                    status = "⚠️ 部分補齊"
                
                print(f"{row['proc_inst_id']:<40} {varinst_dims:<25} {mdm_dims:<25} {status}")
        
        # 5. 總結統計
        print(f"\n📊 步驟 5：總結統計")
        
        summary_query = f"""
        WITH target_proc_inst AS (
            SELECT arrayJoin([{','.join([f"'{pid}'" for pid in target_proc_inst_ids])}]) AS proc_inst_id
        )
        
        SELECT 
            COUNT(*) AS total_proc_inst,
            
            COUNT(*) - COUNT(v_region.PROC_INST_ID_) AS varinst_region_missing,
            COUNT(*) - COUNT(v_plant.PROC_INST_ID_) AS varinst_plant_missing,
            COUNT(*) - COUNT(v_factory.PROC_INST_ID_) AS varinst_factory_missing,
            COUNT(*) - COUNT(v_line.PROC_INST_ID_) AS varinst_line_missing,
            
            COUNT(mdm_region.PROC_INST_ID_) AS mdm_region_success,
            COUNT(mdm_plant.PROC_INST_ID_) AS mdm_plant_success,
            COUNT(mdm_factory.PROC_INST_ID_) AS mdm_factory_success,
            COUNT(mdm_line.PROC_INST_ID_) AS mdm_line_success
            
        FROM target_proc_inst AS t
        LEFT JOIN (
            SELECT DISTINCT PROC_INST_ID_ 
            FROM bronze.bpm_act_hi_varinst 
            WHERE NAME_ = 'region' AND TEXT_ IS NOT NULL AND TEXT_ != ''
        ) AS v_region ON t.proc_inst_id = v_region.PROC_INST_ID_
        LEFT JOIN (
            SELECT DISTINCT PROC_INST_ID_ 
            FROM bronze.bpm_act_hi_varinst 
            WHERE NAME_ = 'plant' AND TEXT_ IS NOT NULL AND TEXT_ != ''
        ) AS v_plant ON t.proc_inst_id = v_plant.PROC_INST_ID_
        LEFT JOIN (
            SELECT DISTINCT PROC_INST_ID_ 
            FROM bronze.bpm_act_hi_varinst 
            WHERE NAME_ = 'factory' AND TEXT_ IS NOT NULL AND TEXT_ != ''
        ) AS v_factory ON t.proc_inst_id = v_factory.PROC_INST_ID_
        LEFT JOIN (
            SELECT DISTINCT PROC_INST_ID_ 
            FROM bronze.bpm_act_hi_varinst 
            WHERE NAME_ = 'lineName' AND TEXT_ IS NOT NULL AND TEXT_ != ''
        ) AS v_line ON t.proc_inst_id = v_line.PROC_INST_ID_
        LEFT JOIN (
            SELECT DISTINCT p.PROC_INST_ID_
            FROM bronze.bpm_act_hi_procinst p
            LEFT JOIN silver.dim_mfg_five_level mdm ON 
                multiIf(p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
                        extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'), '') = mdm.line_name
            WHERE mdm.region_code IS NOT NULL
        ) AS mdm_region ON t.proc_inst_id = mdm_region.PROC_INST_ID_
        LEFT JOIN (
            SELECT DISTINCT p.PROC_INST_ID_
            FROM bronze.bpm_act_hi_procinst p
            LEFT JOIN silver.dim_mfg_five_level mdm ON 
                multiIf(p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
                        extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'), '') = mdm.line_name
            WHERE mdm.plant_code IS NOT NULL
        ) AS mdm_plant ON t.proc_inst_id = mdm_plant.PROC_INST_ID_
        LEFT JOIN (
            SELECT DISTINCT p.PROC_INST_ID_
            FROM bronze.bpm_act_hi_procinst p
            LEFT JOIN silver.dim_mfg_five_level mdm ON 
                multiIf(p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
                        extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'), '') = mdm.line_name
            WHERE mdm.factory_code IS NOT NULL
        ) AS mdm_factory ON t.proc_inst_id = mdm_factory.PROC_INST_ID_
        LEFT JOIN (
            SELECT DISTINCT p.PROC_INST_ID_
            FROM bronze.bpm_act_hi_procinst p
            LEFT JOIN silver.dim_mfg_five_level mdm ON 
                multiIf(p.BUSINESS_KEY_ LIKE '%"lineName":"%', 
                        extract(p.BUSINESS_KEY_, '"lineName":"([^"]+)"'), '') = mdm.line_name
            WHERE mdm.line_name IS NOT NULL
        ) AS mdm_line ON t.proc_inst_id = mdm_line.PROC_INST_ID_
        """
        
        summary_result = client.query(summary_query)
        if summary_result.result_rows:
            stats = summary_result.result_rows[0]
            total = stats[0]
            
            print("✅ 總結統計:")
            print(f"   驗證樣本總數: {total}")
            print(f"   VARINST 缺失統計:")
            print(f"      Region 缺失: {stats[1]}/{total} ({stats[1]/total*100:.1f}%)")
            print(f"      Plant 缺失: {stats[2]}/{total} ({stats[2]/total*100:.1f}%)")
            print(f"      Factory 缺失: {stats[3]}/{total} ({stats[3]/total*100:.1f}%)")
            print(f"      Line 缺失: {stats[4]}/{total} ({stats[4]/total*100:.1f}%)")
            print(f"   MDM 補齊成功統計:")
            print(f"      Region 補齊: {stats[5]}/{total} ({stats[5]/total*100:.1f}%)")
            print(f"      Plant 補齊: {stats[6]}/{total} ({stats[6]/total*100:.1f}%)")
            print(f"      Factory 補齊: {stats[7]}/{total} ({stats[7]/total*100:.1f}%)")
            print(f"      Line 補齊: {stats[8]}/{total} ({stats[8]/total*100:.1f}%)")
        
        return {
            'varinst_content': df_varinst if 'df_varinst' in locals() else None,
            'dimension_missing': df_dimension if 'df_dimension' in locals() else None,
            'mdm_mapping': df_mdm if 'df_mdm' in locals() else None,
            'comparison': df_comparison if 'df_comparison' in locals() else None,
            'summary_stats': stats if 'stats' in locals() else None
        }
        
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    
    finally:
        client.close()

if __name__ == "__main__":
    result = main()
    if result:
        print(f"\n✅ 驗證完成")
    else:
        print("\n❌ 驗證失敗")