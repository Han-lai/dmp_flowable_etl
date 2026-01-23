#!/usr/bin/env python3
"""
只重建 Silver 層 MVIEW
"""

import clickhouse_connect
import sys

def main():
    try:
        # 連接 ClickHouse
        client = clickhouse_connect.get_client(
            host='10.136.218.207',
            port=8121,
            username='default',
            password='default'
        )
        
        print("✅ 連接 ClickHouse 成功")
        
        # 清理現有 Silver MVIEW
        print("🧹 清理現有 Silver MVIEW...")
        cleanup_sql = [
            "DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution",
            "DROP VIEW IF EXISTS silver.vw_fact_task_vx_attribution_realtime"
        ]
        
        for sql in cleanup_sql:
            try:
                client.command(sql)
                print(f"   ✅ {sql}")
            except Exception as e:
                print(f"   ⚠️ {sql} - {e}")
        
        # 重建 Silver 事實表 MVIEW
        print("🔧 重建 Silver 事實表 MVIEW...")
        
        create_mview_sql = """
CREATE MATERIALIZED VIEW silver.mv_fact_task_vx_attribution
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
    toDateOrNull(toString(t.END_TIME_)) AS task_end_date,
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
    
    t.TASK_DEF_KEY_ AS task_definition_key,
    t.NAME_ AS task_name,
    
    -- 人員資訊
    he.EmpName AS task_assignee_name,
    t.ASSIGNEE_ AS task_assignee_account,
    
    -- 預計算：Vx 歸屬
    CASE 
        WHEN COALESCE(v.varinst_moNumber, '') LIKE '196%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
             OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
             OR COALESCE(v.varinst_moNumber, '') LIKE '315%'
        THEN 'V1'
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
        WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
        WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
        ELSE COALESCE(substring(t.TASK_DEF_KEY_, 1, 2), 'Unknown')
    END AS vx_type,
    
    -- 預計算：V1 子類型
    CASE 
        WHEN (COALESCE(v.varinst_moNumber, '') LIKE '196%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
              OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
              OR COALESCE(v.varinst_moNumber, '') LIKE '315%')
             AND v.varinst_name LIKE '%NPE%'
        THEN 'V1_NPE'
        WHEN (COALESCE(v.varinst_moNumber, '') LIKE '196%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '199%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
              OR COALESCE(v.varinst_moNumber, '') LIKE '210%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '212%' 
              OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
              OR COALESCE(v.varinst_moNumber, '') LIKE '315%')
        THEN 'V1_MFG'
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' AND v.varinst_name LIKE '%NPE%'
        THEN 'V1_NPE'
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%'
        THEN 'V1_MFG'
        ELSE NULL
    END AS vx_subtype,
    
    -- 是否套用特殊 V1 規則
    CASE 
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 1
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
        WHEN t.TASK_DEF_KEY_ LIKE 'E%' OR t.TASK_DEF_KEY_ LIKE 'C%' THEN 1
        WHEN COALESCE(v.varinst_moNumber, '') LIKE 'Q%' 
             OR COALESCE(v.varinst_moNumber, '') LIKE 'R%' THEN 1
        ELSE 0
    END AS is_excluded,
    
    -- 排除原因
    CASE 
        WHEN COALESCE(CASE WHEN tb.LONG_ = 1 THEN 'Y' ELSE 'N' END, 'N') != 'N' THEN 'bypass'
        WHEN t.TASK_DEF_KEY_ LIKE 'E%' THEN 'E_prefix'
        WHEN t.TASK_DEF_KEY_ LIKE 'C%' THEN 'C_prefix'
        WHEN COALESCE(v.varinst_moNumber, '') LIKE 'Q%' THEN 'Q_order'
        WHEN COALESCE(v.varinst_moNumber, '') LIKE 'R%' THEN 'R_order'
        ELSE NULL
    END AS exclude_reason,
    
    -- 維度
    COALESCE(v.varinst_plant, '') AS plant,
    COALESCE(v.varinst_factory, '') AS factory,
    COALESCE(v.varinst_lineName, '') AS line,
    
    -- 關聯欄位
    t.PROC_INST_ID_ AS proc_inst_id,
    p.BUSINESS_KEY_ AS business_key,
    COALESCE(v.varinst_moNumber, '') AS mo_number,
    p.NAME_ AS proc_name,
    
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
WHERE t.ID_ IS NOT NULL 
  AND t.ID_ != ''
        """
        
        client.command(create_mview_sql)
        print("   ✅ Silver 事實表 MVIEW 建立成功")
        
        # 建立查詢視圖
        print("🔧 建立查詢視圖...")
        
        create_view_sql = """
CREATE VIEW silver.vw_fact_task_vx_attribution_realtime AS
SELECT 
    task_id,
    task_create_date,
    task_end_date,
    task_create_time,
    task_claim_time,
    task_end_time,
    task_status,
    task_bypass,
    task_definition_key,
    task_name,
    task_assignee_name,
    task_assignee_account,
    vx_type,
    vx_subtype,
    is_special_v1_rule,
    is_excluded,
    exclude_reason,
    plant,
    factory,
    line,
    proc_inst_id,
    business_key,
    mo_number,
    proc_name,
    _mview_update_time AS _transform_time
FROM silver.mv_fact_task_vx_attribution FINAL
        """
        
        client.command(create_view_sql)
        print("   ✅ 查詢視圖建立成功")
        
        # 驗證結果
        print("🔍 驗證結果...")
        
        # 檢查總記錄數
        result = client.query("SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution FINAL")
        total_count = result.result_rows[0][0]
        print(f"   📊 Silver 事實表總記錄數: {total_count}")
        
        # 檢查關鍵測試案例
        test_sql = """
SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution FINAL
WHERE (
    toDate(task_create_time) = '2025-12-25'
    OR toDate(task_claim_time) = '2025-12-25'
    OR toDate(task_end_time) = '2025-12-25'
)
AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
        """
        
        result = client.query(test_sql)
        test_count = result.result_rows[0][0]
        print(f"   📊 WJ2/NBU/E5 2025-12-25 記錄數: {test_count}")
        
        if test_count == 5:
            print("   ✅ 測試通過！記錄數與 MSSQL 一致")
        else:
            print(f"   ⚠️ 測試未通過，預期 5 筆，實際 {test_count} 筆")
        
        print("\n🎉 Silver 層重建完成")
        return True
        
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        return False
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)