#!/usr/bin/env python3
"""
部署 MDM 整合版本 MVIEW
階段 1：並行部署策略
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clickhouse_connect
from datetime import datetime

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

def deploy_mdm_integrated_mview(client):
    """部署 MDM 整合版本 MVIEW"""
    print("🚀 開始部署 MDM 整合版本 MVIEW")
    print("="*60)
    
    # 1. 刪除測試表
    print("1. 清理測試表...")
    client.command("DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution_mdm_test")
    print("   ✅ 完成")
    
    # 2. 建立完整版 MDM 整合 MVIEW
    print("2. 建立 MDM 整合 MVIEW...")
    
    create_mview_sql = """
    CREATE MATERIALIZED VIEW silver.mv_fact_task_vx_attribution_mdm
    ENGINE = ReplacingMergeTree(_mview_update_time)
    ORDER BY (task_id)
    SETTINGS allow_nullable_key = 1
    POPULATE
    AS
    SELECT
        -- 主鍵
        t.ID_ AS task_id,
        
        -- 時間維度
        COALESCE(toDate(t.START_TIME_), toDate('1970-01-01')) AS task_create_date,
        toDateOrNull(t.END_TIME_) AS task_end_date,
        t.START_TIME_ AS task_create_time,
        t.CLAIM_TIME_ AS task_claim_time,
        t.END_TIME_ AS task_end_time,
        
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
        
        -- Vx 歸屬邏輯（修正後的邏輯：工單號規則優先級最高）
        CASE 
            -- 優先級 1：工單號規則（最高，覆蓋所有 TaskDefinitionKey）
            WHEN COALESCE(v.varinst_moNumber, '') LIKE '196%' 
                 OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
                 OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
                 OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
                 OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
                 OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
                 OR COALESCE(v.varinst_moNumber, '') LIKE '315%'
            THEN 'V1'
            
            -- 優先級 2：TaskDefinitionKey 前綴（當工單號規則不符合時）
            WHEN COALESCE(t.TASK_DEF_KEY_, '') LIKE 'V1%' THEN 'V1'
            WHEN COALESCE(t.TASK_DEF_KEY_, '') LIKE 'V2%' THEN 'V2'
            WHEN COALESCE(t.TASK_DEF_KEY_, '') LIKE 'V3%' THEN 'V3'
            
            -- 預設值
            ELSE COALESCE(substring(COALESCE(t.TASK_DEF_KEY_, ''), 1, 2), 'Unknown')
        END AS vx_type,
        
        -- V1 子類型（修正後的邏輯：工單號規則優先，NPE 判別使用 varinst_name 欄位）
        CASE 
            -- 工單號規則的 V1 任務（無論原始 TaskDefinitionKey 是什麼）
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
            
            -- TaskDefinitionKey 的 V1 任務（工單號規則不符合時）
            WHEN COALESCE(t.TASK_DEF_KEY_, '') LIKE 'V1%' AND COALESCE(v.varinst_name, '') LIKE '%NPE%'
            THEN 'V1_NPE'
            
            WHEN COALESCE(t.TASK_DEF_KEY_, '') LIKE 'V1%'
            THEN 'V1_MFG'
            
            -- 其他情況（V2/V3 等）
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
        COALESCE(
            mdm.plant_code,
            v.varinst_plant,
            ''
        ) AS plant,  -- 相容性欄位
        
        COALESCE(
            mdm.factory_code,
            v.varinst_factory,
            ''
        ) AS factory,  -- 相容性欄位
        
        COALESCE(
            mdm.line_name,
            v.varinst_lineName,
            ''
        ) AS line,  -- 相容性欄位
        
        -- ========================================
        -- 其他欄位
        -- ========================================
        
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
    -- TaskBypass 來自任務層級變數 autoComplete
    LEFT JOIN bronze.bpm_act_hi_varinst tb
        ON t.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'
    -- 透過 Line Name 串接 MDM 五階維度表
    LEFT JOIN silver.dim_mfg_five_level mdm 
        ON COALESCE(v.varinst_lineName, '') = mdm.line_name
    WHERE t.ID_ IS NOT NULL 
      AND t.ID_ != ''
    """
    
    try:
        client.command("DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution_mdm")
        client.command(create_mview_sql)
        print("   ✅ MVIEW 建立完成")
        
        # 檢查記錄數
        result = client.query("SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution_mdm")
        record_count = result.result_rows[0][0]
        print(f"   📊 記錄數: {record_count:,}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ MVIEW 建立失敗: {e}")
        return False

def validate_deployment(client):
    """驗證部署結果"""
    print("\\n3. 驗證部署結果...")
    
    try:
        # 檢查維度覆蓋率
        result = client.query("""
        SELECT 
            vx_type,
            COUNT(*) as total,
            round(COUNT(CASE WHEN region_code != '' THEN 1 END) * 100.0 / COUNT(*), 1) as region_pct,
            round(COUNT(CASE WHEN plant_code != '' THEN 1 END) * 100.0 / COUNT(*), 1) as plant_pct,
            round(COUNT(CASE WHEN factory_code != '' THEN 1 END) * 100.0 / COUNT(*), 1) as factory_pct,
            round(COUNT(CASE WHEN line_code != '' THEN 1 END) * 100.0 / COUNT(*), 1) as line_pct
        FROM silver.mv_fact_task_vx_attribution_mdm FINAL
        WHERE vx_type IN ('V1', 'V2', 'V3')
        GROUP BY vx_type
        ORDER BY total DESC
        """)
        
        print("   📊 各 Vx 類型維度覆蓋率:")
        print("   " + "-" * 55)
        print("   Vx       Total      Region%  Plant%   Factory% Line%")
        print("   " + "-" * 55)
        
        for row in result.result_rows:
            vx = row[0]
            total = row[1]
            r_pct = row[2]
            p_pct = row[3]
            f_pct = row[4]
            l_pct = row[5]
            print(f"   {vx:<8} {total:<10,} {r_pct:<8}% {p_pct:<8}% {f_pct:<9}% {l_pct:<8}%")
        
        # 檢查資料來源分布
        result = client.query("""
        SELECT 
            dimension_source,
            COUNT(*) as count,
            round(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution_mdm FINAL), 2) as percentage
        FROM silver.mv_fact_task_vx_attribution_mdm FINAL
        GROUP BY dimension_source
        ORDER BY count DESC
        """)
        
        print("\\n   📊 維度資料來源分布:")
        for row in result.result_rows:
            source = row[0]
            count = row[1]
            pct = row[2]
            print(f"   {source}: {count:,} ({pct}%)")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 驗證失敗: {e}")
        return False

def main():
    """主執行函數"""
    try:
        print("🚀 開始部署 MDM 整合版本 MVIEW")
        print("="*80)
        
        # 建立連線
        client = get_clickhouse_client()
        if client is None:
            return False
        
        # 1. 部署 MDM 整合 MVIEW
        if not deploy_mdm_integrated_mview(client):
            return False
        
        # 2. 驗證部署結果
        if not validate_deployment(client):
            return False
        
        print("\\n✅ MDM 整合版本 MVIEW 部署完成")
        print("📋 下一步：可以開始對比測試新舊版本的資料一致性")
        
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