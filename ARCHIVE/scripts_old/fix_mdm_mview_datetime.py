#!/usr/bin/env python3
"""
修正 MDM 整合 MVIEW 的時間欄位問題
使用 NULL 安全的時間處理方式
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clickhouse_connect

def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    try:
        client = clickhouse_connect.get_client(
            host='REDACTED_IP',
            port=8121,
            username='default',
            password='default'
        )
        return client
    except Exception as e:
        print(f"❌ ClickHouse 連線失敗: {e}")
        return None

def deploy_fixed_mdm_mview(client):
    """部署修正後的 MDM 整合 MVIEW"""
    print("🔧 部署修正後的 MDM 整合 MVIEW")
    print("="*50)
    
    # 刪除現有表
    print("1. 清理現有表...")
    client.command("DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution_mdm")
    
    # 建立修正版 MVIEW
    print("2. 建立修正版 MDM 整合 MVIEW...")
    
    create_sql = """
    CREATE TABLE silver.mv_fact_task_vx_attribution_mdm
    ENGINE = ReplacingMergeTree(_mview_update_time)
    ORDER BY (task_id)
    AS
    SELECT
        -- 主鍵
        t.ID_ AS task_id,
        
        -- 時間維度 (修正 NULL 值處理)
        COALESCE(toDate(t.START_TIME_), toDate('1970-01-01')) AS task_create_date,
        t.START_TIME_ AS task_create_time,
        CASE WHEN t.CLAIM_TIME_ IS NOT NULL THEN t.CLAIM_TIME_ ELSE NULL END AS task_claim_time,
        CASE WHEN t.END_TIME_ IS NOT NULL THEN t.END_TIME_ ELSE NULL END AS task_end_time,
        
        -- 任務屬性
        COALESCE(
            CASE 
                WHEN t.END_TIME_ IS NOT NULL THEN 'DONE'
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

def validate_fixed_mview(client):
    """驗證修正後的 MVIEW"""
    print("\n3. 驗證修正後的 MVIEW...")
    
    try:
        # 檢查時間欄位是否正常
        time_check = client.query("""
        SELECT 
            COUNT(*) as total,
            COUNT(task_create_time) as has_create_time,
            COUNT(task_claim_time) as has_claim_time,
            COUNT(task_end_time) as has_end_time
        FROM silver.mv_fact_task_vx_attribution_mdm
        """)
        
        if time_check.result_rows:
            total, create_time, claim_time, end_time = time_check.result_rows[0]
            print(f"   時間欄位統計:")
            print(f"   總記錄: {total:,}")
            print(f"   有建立時間: {create_time:,}")
            print(f"   有認領時間: {claim_time:,}")
            print(f"   有結束時間: {end_time:,}")
        
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
        print("   Vx   | Region% | Plant% | Factory% | Line%")
        print("   " + "="*40)
        for row in dimension_check.result_rows:
            vx, total, region_pct, plant_pct, factory_pct, line_pct = row
            print(f"   {vx:<4} | {region_pct:<7}% | {plant_pct:<6}% | {factory_pct:<8}% | {line_pct:<5}%")
        
        # 檢查資料來源分布
        source_check = client.query("""
        SELECT 
            dimension_source,
            COUNT(*) as count,
            round(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution_mdm), 2) as percentage
        FROM silver.mv_fact_task_vx_attribution_mdm
        GROUP BY dimension_source
        ORDER BY count DESC
        """)
        
        print(f"\n   維度資料來源分布:")
        for row in source_check.result_rows:
            source, count, pct = row
            print(f"   {source}: {count:,} ({pct}%)")
        
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
        if not deploy_fixed_mdm_mview(client):
            return False
        
        # 2. 驗證修正後的 MVIEW
        if not validate_fixed_mview(client):
            return False
        
        print("\n✅ MDM 整合 MVIEW 時間欄位修正完成")
        print("📋 修正內容:")
        print("   - 使用 CASE WHEN 處理 NULL 時間欄位")
        print("   - 使用 COALESCE + toDate 處理日期轉換")
        print("   - 保持完整的 MDM 維度整合功能")
        
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