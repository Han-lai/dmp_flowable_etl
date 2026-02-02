#!/usr/bin/env python3
"""
深入分析 FlowableTaskStats vs BPM 原生表的差異

確認 FlowableTaskStats 的 TaskId 是否存在於 BPM 原生表
"""

import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    print("=" * 80)
    print("FlowableTaskStats vs BPM 原生表差異分析")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    target_date = '2025-12-25'
    
    # ========================================
    # 1. 取得 Bronze 層的 Task ID
    # ========================================
    print("\n" + "=" * 80)
    print("📊 1. 取得 Bronze 層 (FlowableTaskStats) 的 Task ID")
    print("=" * 80)
    
    bronze_sql = f"""
        SELECT 
            TaskId,
            ProcessInstanceId,
            TaskDefinitionKey,
            TaskStatus,
            Plant,
            Factory,
            Line
        FROM bronze.common_flowable_task_stats FINAL
        WHERE Plant = '{plant}'
          AND Factory = '{factory}'
          AND Line = '{line}'
          AND (TaskBypass = 'N' OR TaskBypass IS NULL)
          AND (toDate(TaskCreateTime) = '{target_date}' 
               OR toDate(TaskClaimTime) = '{target_date}' 
               OR toDate(TaskEndTime) = '{target_date}')
        LIMIT 10
    """
    result = client.query(bronze_sql)
    
    bronze_task_ids = []
    bronze_proc_ids = []
    
    print("\n   Bronze 樣本資料:")
    for row in result.result_rows:
        task_id = row[0]
        proc_id = row[1]
        task_def = row[2]
        status = row[3]
        print(f"      TaskId: {task_id}")
        print(f"      ProcessInstanceId: {proc_id}")
        print(f"      TaskDefKey: {task_def}, Status: {status}")
        print()
        bronze_task_ids.append(task_id)
        bronze_proc_ids.append(proc_id)
    
    # ========================================
    # 2. 檢查這些 Task ID 是否存在於 BPM 原生表
    # ========================================
    print("\n" + "=" * 80)
    print("📊 2. 檢查 Bronze Task ID 是否存在於 BPM 原生表")
    print("=" * 80)
    
    if bronze_task_ids:
        task_id_list = "', '".join(bronze_task_ids[:5])
        check_sql = f"""
            SELECT ID_, TASK_DEF_KEY_, PROC_INST_ID_
            FROM bronze.bpm_act_hi_taskinst
            WHERE ID_ IN ('{task_id_list}')
        """
        result = client.query(check_sql)
        print(f"\n   在 bpm_act_hi_taskinst 找到: {len(result.result_rows)} 筆")
        for row in result.result_rows:
            print(f"      {row[0]}: {row[1]}")
    
    # ========================================
    # 3. 檢查 ProcessInstanceId 是否存在
    # ========================================
    print("\n" + "=" * 80)
    print("📊 3. 檢查 Bronze ProcessInstanceId 是否存在於 BPM 原生表")
    print("=" * 80)
    
    if bronze_proc_ids:
        proc_id_list = "', '".join([p for p in bronze_proc_ids[:5] if p])
        if proc_id_list:
            check_sql = f"""
                SELECT PROC_INST_ID_, count() as task_count
                FROM bronze.bpm_act_hi_taskinst
                WHERE PROC_INST_ID_ IN ('{proc_id_list}')
                GROUP BY PROC_INST_ID_
            """
            result = client.query(check_sql)
            print(f"\n   在 bpm_act_hi_taskinst 找到的 ProcessInstance:")
            for row in result.result_rows:
                print(f"      {row[0]}: {row[1]} 個任務")
    
    # ========================================
    # 4. 檢查 BPM 原生表中的 E5 任務
    # ========================================
    print("\n" + "=" * 80)
    print("📊 4. BPM 原生表 + VARINST 查詢 E5 任務")
    print("=" * 80)
    
    # 透過 VARINST 取得 Plant/Factory/Line 資訊
    bpm_sql = f"""
        SELECT 
            t.ID_ as task_id,
            t.TASK_DEF_KEY_,
            t.START_TIME_,
            v.varinst_plant,
            v.varinst_factory,
            v.varinst_lineName
        FROM bronze.bpm_act_hi_taskinst t
        LEFT JOIN silver.mv_varinst_pivoted v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
        WHERE v.varinst_plant = '{plant}'
          AND v.varinst_factory = '{factory}'
          AND v.varinst_lineName = '{line}'
          AND (toDate(t.START_TIME_) = '{target_date}'
               OR toDate(t.CLAIM_TIME_) = '{target_date}'
               OR toDate(t.END_TIME_) = '{target_date}')
        LIMIT 10
    """
    result = client.query(bpm_sql)
    
    bpm_task_ids = []
    print(f"\n   BPM 原生表樣本 (透過 VARINST 匹配):")
    for row in result.result_rows:
        print(f"      {row[0]}: {row[1]} | {row[2]} | {row[3]}/{row[4]}/{row[5]}")
        bpm_task_ids.append(row[0])
    
    # ========================================
    # 5. 交叉比對 Task ID
    # ========================================
    print("\n" + "=" * 80)
    print("📊 5. Task ID 交叉比對")
    print("=" * 80)
    
    bronze_set = set(bronze_task_ids)
    bpm_set = set(bpm_task_ids)
    
    intersection = bronze_set & bpm_set
    print(f"\n   Bronze Task IDs: {bronze_set}")
    print(f"\n   BPM Task IDs: {bpm_set}")
    print(f"\n   交集: {intersection}")
    
    # ========================================
    # 6. 檢查 FlowableTaskStats 的來源邏輯
    # ========================================
    print("\n" + "=" * 80)
    print("📊 6. 分析 FlowableTaskStats 的資料範圍")
    print("=" * 80)
    
    # 總筆數比較
    flowable_total = client.command("SELECT count() FROM bronze.common_flowable_task_stats FINAL")
    bpm_total = client.command("SELECT count() FROM bronze.bpm_act_hi_taskinst")
    
    print(f"\n   FlowableTaskStats 總筆數: {flowable_total:,}")
    print(f"   BPM ACT_HI_TASKINST 總筆數: {bpm_total:,}")
    print(f"   差異: {bpm_total - flowable_total:,} ({(bpm_total/flowable_total - 1)*100:.1f}%)")
    
    # 檢查 FlowableTaskStats 的時間範圍
    time_range_sql = """
        SELECT 
            min(TaskCreateTime) as min_create,
            max(TaskCreateTime) as max_create
        FROM bronze.common_flowable_task_stats FINAL
    """
    result = client.query(time_range_sql)
    print(f"\n   FlowableTaskStats 時間範圍: {result.result_rows[0][0]} ~ {result.result_rows[0][1]}")
    
    # ========================================
    # 7. 檢查維度來源差異
    # ========================================
    print("\n" + "=" * 80)
    print("📊 7. 維度欄位來源差異分析")
    print("=" * 80)
    
    # FlowableTaskStats 的維度欄位直接來自表
    # Silver 的維度來自 VARINST 或 MDM 補齊
    
    print("\n   FlowableTaskStats 維度欄位的來源:")
    print("   - Plant, Factory, Line 直接存儲於 FlowableTaskStats")
    print("   - 這些可能來自 MSSQL 端的預計算/ETL")
    
    print("\n   Silver mv_fact_task_vx 維度欄位的來源:")
    print("   - 優先使用 VARINST (varinst_plant, varinst_factory, varinst_lineName)")
    print("   - 補齊使用 MDM (mv_dim_mfg_five_level)")
    
    # 檢查 Silver 層維度來源分布
    source_sql = f"""
        SELECT 
            plant_source,
            count() as cnt
        FROM silver.mv_fact_task_vx FINAL
        WHERE plant = '{plant}'
          AND factory = '{factory}'
          AND line = '{line}'
          AND is_excluded = 0
        GROUP BY plant_source
    """
    result = client.query(source_sql)
    print(f"\n   Silver E5 任務的維度來源分布:")
    for row in result.result_rows:
        print(f"      {row[0]}: {row[1]}")
    
    print("\n" + "=" * 80)
    print("📋 結論")
    print("=" * 80)
    print("""
   ⚠️ FlowableTaskStats 和 BPM 原生表是兩個完全不同的資料來源：
   
   1. FlowableTaskStats (Bronze)
      - 來源: MSSQL APP_SRV_COMMON.dbo.FlowableTaskStats
      - 這是一個預聚合/ETL後的表
      - 維度 (Plant/Factory/Line) 已在 MSSQL 端處理
      
   2. BPM 原生表 (Silver 的來源)
      - 來源: bronze.bpm_act_hi_taskinst (同步自 APP_SRV_BPM)
      - 維度來自 VARINST 或 MDM 補齊
      - 這是原始的 Flowable BPM 資料
   
   3. 如果要讓 Silver 與 FlowableTaskStats 一致，需要：
      - 確認 FlowableTaskStats 的過濾邏輯
      - 或直接使用 FlowableTaskStats 作為資料來源（而非 BPM 原生表）
    """)
    
    client.close()

if __name__ == "__main__":
    main()
