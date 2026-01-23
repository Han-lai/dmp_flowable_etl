#!/usr/bin/env python3
"""
修正 MDM 整合 MVIEW 的時間欄位問題 - 第二版
完全避開 NULL 值問題，使用字串轉換
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clickhouse_connect

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    try:
        client = clickhouse_connect.get_client(
            host='10.136.218.207',
            port=8121,
            username='default',
            password='default'
        )
        return client
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        return None

def deploy_fixed_mdm_mview_v2(client):
    """部署修正後的 MDM 整合 MVIEW - 第二版"""
    print("🔧 部署修正後的 MDM 整合 MVIEW (V2)")
    print("="*50)
    
    # 刪除現有表
    print("1. 清理現有表...")
    client.command("DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution_mdm")
    
    # 建立修正版 MVIEW - 使用字串轉換避開 NULL 問題
    print("2. 建立修正版 MDM 整合 MVIEW...")
    
    create_sql = """
    CREATE TABLE silver.mv_fact_task_vx_attribution_mdm
    ENGINE = ReplacingMergeTree(_mview_update_time)
    ORDER BY (task_id)
    AS
    SELECT
        -- 主鍵
        t.ID_ AS task_id,
        
        -- 時間維度 (使用字串轉換避開 NULL 問題)
        toDate(toString(t.START_TIME_)) AS task_create_date,
        toString(t.START_TIME_) AS task_create_time,
        toString(t.CLAIM_TIME_) AS task_claim_time,
        toString(t.END_TIME_) AS task_end_time,
        
        -- 任務屬性
        COALESCE(
            CASE 
                WHEN toString(t.END_TIME_) != '1900-01-01 00:00:00.000000' THEN 'DONE'
                WHEN t.ASSIGNEE_ IS NOT NULL AND t.ASSIGNEE_ != '' THEN 'DOING' 
                ELSE 'TODO'
            END, 
            'Unknown'
        ) AS task_status,
        
        COALESCE(
            CASE WHEN tb.LONG_ = 1 THEN 'Y' ELSE 'N' END, 
            'N'
        ) AS task_bypass,
        
        COALESCE(t.TASK_DEF_KEY_, '') AS task_definition_key,
        COALESCE(t.NAME_, '') AS task_name,
        
        -- 人員資訊
        COALESCE(he.EmpName, '') AS task_assignee_name,
        COALESCE(t.ASSIGNEE_, '') AS task_assignee_account,
        
        -- Vx 歸屬邏輯
        CASE 
            WHEN COALESCE(v.varinst_moNumber, '') LIKE '196%' 
                 OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
                 OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
                 OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
                 OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
                 OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
                 OR COALESCE(v.varinst_moNumber, '') LIKE '315%'
            THEN 'V1'
            WHEN COALESCE(t.TASK_DEF_KEY_, '') LIKE 'V1%' THEN 'V1'
            WHEN COALESCE(t.TASK_DEF_KEY_, '') LIKE 'V2%' THEN 'V2'
            WHEN COALESCE(t.TASK_DEF_KEY_, '') LIKE 'V3%' THEN 'V3'
            ELSE COALESCE(substring(COALESCE(t.TASK_DEF_KEY_, ''), 1, 2), 'Unknown')
        END AS vx_type,
        
        -- V1 子類型
        CASE 
            WHEN (COALESCE(v.varinst_moNumber, '') LIKE '196%' 
                  OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
                  OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
                  OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
                  OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
                  OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
                  OR COALESCE(v.varinst_moNumber, '') LIKE '315%')
                 AND COALESCE(v.varinst_name, '') LIKE '%NPE%'
            THEN 'V1_NPE'
            WHEN (COALESCE(v.varinst_moNumber, '') LIKE '196%' 
                  OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
                  OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
                  OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
                  OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
                  OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
                  OR COALESCE(v.varinst_moNumber, '') LIKE '315%')
            THEN 'V1_MFG'
            WHEN COALESCE(t.TASK_DEF_KEY_, '') LIKE 'V1%' AND COALESCE(v.varinst_name, '') LIKE '%NPE%'
            THEN 'V1_NPE'
            WHEN COALESCE(t.TASK_DEF_KEY_, '') LIKE 'V1%'
            THEN 'V1_MFG'
            ELSE NULL
        END AS vx_subtype,
        
        -- ========================================
        -- 製造五階維度（MDM 整合版本）
        -- ========================================
        
        -- Region 層級（MDM 主來源）
        COALESCE(mdm.region_code, '') AS region_code,
        COALESCE(mdm.region_name, '') AS region_name,
        
        -- Plant 層級（MDM 主來源，Flowable 輔助）
        COALESCE(
            mdm.plant_code,         -- MDM 主來源
            v.varinst_plant,        -- Flowable 輔助來源
            ''
        ) AS plant_code,
        COALESCE(mdm.plant_name, '') AS plant_name,
        
        -- Factory 層級（MDM 主來源，Flowable 輔助）
        COALESCE(
            mdm.factory_code,       -- MDM 主來源
            v.varinst_factory,      -- Flowable 輔助來源
            ''
        ) AS factory_code,
        COALESCE(mdm.factory_name, '') AS factory_name,
        
        -- Line 層級（MDM 主來源，Flowable 輔助）
        COALESCE(
            mdm.line_name,          -- MDM 主來源
            v.varinst_lineName,     -- Flowable 輔助來源
            ''
        ) AS line_code,
        COALESCE(mdm.line_desc, '') AS line_name,
        
        -- 維度資料來源標記
        CASE 
            WHEN mdm.line_name IS NOT NULL THEN 'MDM_PRIMARY'
            WHEN COALESCE(v.varinst_lineName, '') != '' THEN 'FLOWABLE_FALLBACK'
            ELSE 'NO_DIMENSION'
        END AS dimension_source,
        
        -- 維度資料品質標記
        COALESCE(mdm.is_valid, 0) AS dimension_is_valid,
        
        -- ========================================
        -- 相容性維度欄位（保持向後相容）
        -- ========================================
        COALESCE(mdm.plant_code, v.varinst_plant, '') AS plant,
        COALESCE(mdm.factory_code, v.varinst_factory, '') AS factory,
        COALESCE(mdm.line_name, v.varinst_lineName, '') AS line,
        
        -- 是否套用特殊 V1 規則
        CASE 
            WHEN COALESCE(t.TASK_DEF_KEY_, '') LIKE 'V1%' THEN 1
            WHEN COALESCE(v.varinst_moNumber, '') LIKE '196%' 
                 OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
                 OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
                 OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
                 OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
                 OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
                 OR COALESCE(v.varinst_moNumber, '') LIKE '315%'
            THEN 1
            ELSE 0
        END AS is_special_v1_rule,
        
        -- 排除標記
        CASE 
            WHEN COALESCE(CASE WHEN tb.LONG_ = 1 THEN 'Y' ELSE 'N' END, 'N') != 'N' THEN 1
            WHEN COALESCE(t.TASK_DEF_KEY_, '') LIKE 'E%' OR COALESCE(t.TASK_DEF_KEY_, '') LIKE 'C%' THEN 1
            WHEN COALESCE(v.varinst_moNumber, '') LIKE 'Q%' 
                 OR COALESCE(v.varinst_moNumber, '') LIKE 'R%' THEN 1
            ELSE 0
        END AS is_excluded,
        
        -- 排除原因
        CASE 
            WHEN COALESCE(CASE WHEN tb.LONG_ = 1 THEN 'Y' ELSE 'N' END, 'N') != 'N' THEN 'bypass'
            WHEN COALESCE(t.TASK_DEF_KEY_, '') LIKE 'E%' THEN 'E_prefix'
            WHEN COALESCE(t.TASK_DEF_KEY_, '') LIKE 'C%' THEN 'C_prefix'
            WHEN COALESCE(v.varinst_moNumber, '') LIKE 'Q%' THEN 'Q_order'
            WHEN COALESCE(v.varinst_moNumber, '') LIKE 'R%' THEN 'R_order'
            ELSE NULL
        END AS exclude_reason,
        
        -- 關聯欄位
        COALESCE(t.PROC_INST_ID_, '') AS proc_inst_id,
        COALESCE(p.BUSINESS_KEY_, '') AS business_key,
        COALESCE(v.varinst_moNumber, '') AS mo_number,
        COALESCE(p.NAME_, '') AS proc_name,
        
        -- Metadata
        now64(3) AS _mview_update_time

    FROM bronze.bpm_act_hi_taskinst t
    LEFT JOIN bronze.bpm_act_hi_procinst p 
        ON t.PROC_INST_ID_ = p.PROC_INST_ID_
    LEFT JOIN silver.mv_varinst_pivoted v
        ON t.PROC_INST_ID_ = v.PROC_INST_ID_
    LEFT JOIN bronze.common_hr_employee he
        ON t.ASSIGNEE_ = he.EmpCode
    LEFT JOIN bronze.bpm_act_hi_varinst tb
        ON t.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'
    LEFT JOIN silver.dim_mfg_five_level mdm 
        ON COALESCE(v.varinst_lineName, '') = mdm.line_name
    WHERE t.ID_ IS NOT NULL 
      AND t.ID_ != ''
    """
    
    try:
        client.command(create_sql)
        print("   ✅ MVIEW 建立完成")
        
        # 檢查記錄數
        result = client.query("SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution_mdm")
        record_count = result.result_rows[0][0]
        print(f"   📊 記錄數: {record_count:,}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ MVIEW 建立失敗: {e}")
        return False

def validate_fixed_mview_v2(client):
    """驗證修正後的 MVIEW - 第二版"""
    print("\n3. 驗證修正後的 MVIEW...")
    
    try:
        # 檢查基本統計
        basic_stats = client.query("""
        SELECT 
            COUNT(*) as total,
            COUNT(DISTINCT vx_type) as vx_types,
            COUNT(CASE WHEN dimension_source = 'MDM_PRIMARY' THEN 1 END) as mdm_primary,
            COUNT(CASE WHEN dimension_source = 'FLOWABLE_FALLBACK' THEN 1 END) as flowable_fallback,
            COUNT(CASE WHEN dimension_source = 'NO_DIMENSION' THEN 1 END) as no_dimension
        FROM silver.mv_fact_task_vx_attribution_mdm
        """)
        
        if basic_stats.result_rows:
            total, vx_types, mdm_primary, flowable_fallback, no_dimension = basic_stats.result_rows[0]
            print(f"   基本統計:")
            print(f"   總記錄: {total:,}")
            print(f"   Vx 類型數: {vx_types}")
            print(f"   MDM 主來源: {mdm_primary:,} ({mdm_primary/total*100:.1f}%)")
            print(f"   Flowable 輔助: {flowable_fallback:,} ({flowable_fallback/total*100:.1f}%)")
            print(f"   無維度: {no_dimension:,} ({no_dimension/total*100:.1f}%)")
        
        # 檢查維度覆蓋率
        dimension_check = client.query("""
        SELECT 
            vx_type,
            COUNT(*) as total,
            round(COUNT(CASE WHEN region_code != '' THEN 1 END) * 100.0 / COUNT(*), 1) as region_pct,
            round(COUNT(CASE WHEN plant_code != '' THEN 1 END) * 100.0 / COUNT(*), 1) as plant_pct,
            round(COUNT(CASE WHEN factory_code != '' THEN 1 END) * 100.0 / COUNT(*), 1) as factory_pct,
            round(COUNT(CASE WHEN line_code != '' THEN 1 END) * 100.0 / COUNT(*), 1) as line_pct
        FROM silver.mv_fact_task_vx_attribution_mdm
        WHERE vx_type IN ('V1', 'V2', 'V3')
        GROUP BY vx_type
        ORDER BY vx_type
        """)
        
        print(f"\n   維度覆蓋率:")
        print("   Vx   | Total   | Region% | Plant% | Factory% | Line%")
        print("   " + "="*50)
        for row in dimension_check.result_rows:
            vx, total, region_pct, plant_pct, factory_pct, line_pct = row
            print(f"   {vx:<4} | {total:<7,} | {region_pct:<7}% | {plant_pct:<6}% | {factory_pct:<8}% | {line_pct:<5}%")
        
        # 檢查時間欄位範例
        time_sample = client.query("""
        SELECT task_id, task_create_time, task_claim_time, task_end_time, task_status
        FROM silver.mv_fact_task_vx_attribution_mdm
        LIMIT 5
        """)
        
        print(f"\n   時間欄位範例:")
        for i, row in enumerate(time_sample.result_rows, 1):
            task_id, create_time, claim_time, end_time, status = row
            print(f"   {i}. {task_id[:8]}... | 建立: {create_time[:19]} | 認領: {claim_time[:19]} | 結束: {end_time[:19]} | 狀態: {status}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 驗證失敗: {e}")
        return False

def main():
    """主執行函數"""
    try:
        # 建立連線
        client = get_clickhouse_client()
        if client is None:
            return False
        
        # 1. 部署修正後的 MDM 整合 MVIEW
        if not deploy_fixed_mdm_mview_v2(client):
            return False
        
        # 2. 驗證修正後的 MVIEW
        if not validate_fixed_mview_v2(client):
            return False
        
        print("\n✅ MDM 整合 MVIEW 時間欄位修正完成 (V2)")
        print("📋 修正內容:")
        print("   - 使用 toString() 轉換時間欄位為字串")
        print("   - 避開 ClickHouse NULL 值類型問題")
        print("   - 保持完整的 MDM 維度整合功能")
        print("   - 成功載入所有任務資料")
        
        return True
        
    except Exception as e:
        print(f"❌ 執行過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            client.close()
        except:
            pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)