#!/usr/bin/env python3
"""
重建 Silver Layer 2 (增加多時間維度)
"""

import clickhouse_connect
from datetime import datetime

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 1800
}

def main():
    print("=" * 80)
    print("重建 Silver Layer 2 (增加多時間維度)")
    print("=" * 80)
    print(f"開始時間: {datetime.now()}")
    
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    # 設定長 timeout
    client.command("SET max_execution_time = 1800")
    client.command("SET send_timeout = 1800")
    client.command("SET receive_timeout = 1800")
    
    try:
        # Step 1: 刪除舊表
        print("\n📦 Step 1: 刪除舊 Silver 表...")
        client.command("DROP TABLE IF EXISTS silver.mv_fact_task_vx")
        print("✅ 舊表已刪除")
        
        # Step 2: 建立新表 (需要較長時間)
        print("\n📦 Step 2: 建立新 Silver 表 (預計 5-10 分鐘)...")
        
        create_sql = """
        CREATE MATERIALIZED VIEW silver.mv_fact_task_vx
        ENGINE = ReplacingMergeTree(_mview_update_time)
        ORDER BY (task_id)
        TTL task_primary_date + INTERVAL 1 YEAR
        SETTINGS allow_nullable_key = 1
        POPULATE AS
        SELECT
            t.ID_ AS task_id,
            
            -- 多時間維度
            toDate(t.START_TIME_) AS task_start_date,
            toDate(t.CLAIM_TIME_) AS task_claim_date,
            toDate(t.END_TIME_) AS task_end_date,
            toDate(COALESCE(t.START_TIME_, t.CLAIM_TIME_, t.END_TIME_)) AS task_primary_date,
            toDate(COALESCE(t.START_TIME_, t.CLAIM_TIME_, t.END_TIME_)) AS task_create_date,
            
            -- 任務狀態
            CASE 
                WHEN t.END_TIME_ IS NOT NULL THEN 'DONE'
                WHEN t.ASSIGNEE_ IS NOT NULL AND t.ASSIGNEE_ != '' THEN 'DOING'
                ELSE 'TODO'
            END AS task_status,
            
            -- Vx 歸屬
            CASE 
                WHEN COALESCE(v.varinst_moNumber, '') LIKE '315%' THEN 'V1'
                WHEN COALESCE(v.varinst_moNumber, '') LIKE '196%' 
                     OR COALESCE(v.varinst_moNumber, '') LIKE '199%'
                     OR COALESCE(v.varinst_moNumber, '') LIKE '200%'
                     OR COALESCE(v.varinst_moNumber, '') LIKE '210%'
                     OR COALESCE(v.varinst_moNumber, '') LIKE '212%'
                     OR COALESCE(v.varinst_moNumber, '') LIKE '213%'
                THEN 'V1'
                WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                ELSE COALESCE(substring(t.TASK_DEF_KEY_, 1, 2), 'Unknown')
            END AS vx_type,
            
            -- 維度
            COALESCE(NULLIF(v.varinst_region, ''), mdm.region_code, 'UNKNOWN') AS region,
            COALESCE(NULLIF(v.varinst_plant, ''), mdm.plant_code, 'UNKNOWN') AS plant,
            COALESCE(NULLIF(v.varinst_factory, ''), mdm.factory_code, 'UNKNOWN') AS factory,
            COALESCE(NULLIF(v.varinst_lineName, ''), mdm.line_name, 'UNKNOWN') AS line,
            
            -- 維度來源
            CASE WHEN v.varinst_region != '' THEN 'VARINST' 
                 WHEN mdm.region_code IS NOT NULL THEN 'MDM' ELSE 'MISSING' END AS region_source,
            CASE WHEN v.varinst_plant != '' THEN 'VARINST'
                 WHEN mdm.plant_code IS NOT NULL THEN 'MDM' ELSE 'MISSING' END AS plant_source,
            CASE WHEN v.varinst_factory != '' THEN 'VARINST'
                 WHEN mdm.factory_code IS NOT NULL THEN 'MDM' ELSE 'MISSING' END AS factory_source,
            CASE WHEN v.varinst_lineName != '' THEN 'VARINST'
                 WHEN mdm.line_name IS NOT NULL THEN 'MDM' ELSE 'MISSING' END AS line_source,
            
            -- 排除標記
            CASE 
                WHEN tb.LONG_ = 1 THEN 1
                WHEN t.TASK_DEF_KEY_ LIKE 'E%' OR t.TASK_DEF_KEY_ LIKE 'C%' THEN 1
                WHEN COALESCE(v.varinst_moNumber, '') LIKE 'Q%' 
                     OR COALESCE(v.varinst_moNumber, '') LIKE 'R%' THEN 1
                ELSE 0
            END AS is_excluded,
            
            CASE 
                WHEN tb.LONG_ = 1 THEN 'bypass'
                WHEN t.TASK_DEF_KEY_ LIKE 'E%' THEN 'E_prefix'
                WHEN t.TASK_DEF_KEY_ LIKE 'C%' THEN 'C_prefix'
                WHEN COALESCE(v.varinst_moNumber, '') LIKE 'Q%' THEN 'Q_order'
                WHEN COALESCE(v.varinst_moNumber, '') LIKE 'R%' THEN 'R_order'
                ELSE NULL
            END AS exclude_reason,
            
            -- 人員資訊
            t.ASSIGNEE_ AS assignee_code,
            he.EmpName AS assignee_name,
            
            -- 任務屬性
            t.TASK_DEF_KEY_ AS task_definition_key,
            t.NAME_ AS task_name,
            v.varinst_moNumber AS mo_number,
            t.PROC_INST_ID_ AS proc_inst_id,
            
            now64(3) AS _mview_update_time

        FROM bronze.bpm_act_hi_taskinst t
        LEFT JOIN silver.mv_varinst_pivoted v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
        LEFT JOIN silver.mv_dim_mfg_five_level mdm ON v.varinst_lineName = mdm.line_name
        LEFT JOIN bronze.common_hr_employee he ON t.ASSIGNEE_ = he.EmpCode
        LEFT JOIN bronze.bpm_act_hi_varinst tb ON t.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'
        WHERE t.ID_ IS NOT NULL AND t.ID_ != ''
        """
        
        import time
        start_time = time.perf_counter()
        client.command(create_sql)
        duration = time.perf_counter() - start_time
        print(f"✅ Silver 表已建立 (耗時 {duration:.1f} 秒)")
        
        # Step 3: 驗證
        print("\n📦 Step 3: 驗證結果...")
        
        count = client.command("SELECT count() FROM silver.mv_fact_task_vx")
        print(f"  總筆數: {count:,}")
        
        # 驗證時間維度
        result = client.query("""
            SELECT 
                countIf(task_start_date IS NOT NULL) AS with_start,
                countIf(task_claim_date IS NOT NULL) AS with_claim,
                countIf(task_end_date IS NOT NULL) AS with_end
            FROM silver.mv_fact_task_vx FINAL
        """)
        if result.result_rows:
            row = result.result_rows[0]
            print(f"  有 task_start_date: {row[0]:,}")
            print(f"  有 task_claim_date: {row[1]:,}")
            print(f"  有 task_end_date: {row[2]:,}")
        
        # 驗證 Vx 分布
        print("\n📊 Vx 分布:")
        result = client.query("""
            SELECT vx_type, count() as cnt
            FROM silver.mv_fact_task_vx FINAL
            WHERE is_excluded = 0
            GROUP BY vx_type
            ORDER BY cnt DESC
        """)
        for row in result.result_rows:
            print(f"  {row[0]}: {row[1]:,}")
        
        print("\n" + "=" * 80)
        print("✅ Silver Layer 2 重建完成！")
        print("=" * 80)
        print(f"完成時間: {datetime.now()}")
        
    except Exception as e:
        print(f"\n❌ 執行失敗: {e}")
        raise
    finally:
        client.close()

if __name__ == "__main__":
    main()
