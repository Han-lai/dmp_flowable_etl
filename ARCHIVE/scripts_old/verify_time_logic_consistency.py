#!/usr/bin/env python3
"""
驗證 MSSQL 和 ClickHouse 時間邏輯一致性
特別檢查 CNE WJ2 NBU E5 在 2025-12-25 的資料
"""

import clickhouse_connect
import sys
from datetime import datetime

def main():
    try:
        # 連接 ClickHouse
        client = clickhouse_connect.get_client(
            host='10.136.218.207',
            port=8121,
            username='default',
            password='default'
        )
        
        print("=== MSSQL vs ClickHouse 時間邏輯一致性驗證 ===\n")
        
        # 1. 檢查 Silver 層的時間展開邏輯
        print("1. 檢查 Silver 層時間展開邏輯")
        print("-" * 50)
        
        query_time_expansion = """
        WITH target_date AS (
            SELECT '2025-12-25' AS check_date
        ),
        time_expansion_check AS (
            SELECT 
                t.ID_ AS task_id,
                t.PROC_INST_ID_,
                t.START_TIME_,
                t.CLAIM_TIME_,
                t.END_TIME_,
                
                -- 模擬 MSSQL OR 條件
                CASE 
                    WHEN (toDate(t.START_TIME_) = '2025-12-25')
                      OR (toDate(t.CLAIM_TIME_) = '2025-12-25')
                      OR (toDate(t.END_TIME_) = '2025-12-25')
                    THEN 1 
                    ELSE 0 
                END AS mssql_should_include,
                
                -- ClickHouse 展開邏輯
                arrayDistinct(arrayFilter(x -> x IS NOT NULL, [
                    toDate(t.START_TIME_),
                    toDate(t.CLAIM_TIME_),
                    toDate(t.END_TIME_)
                ])) AS expanded_dates,
                
                has(arrayDistinct(arrayFilter(x -> x IS NOT NULL, [
                    toDate(t.START_TIME_),
                    toDate(t.CLAIM_TIME_),
                    toDate(t.END_TIME_)
                ])), toDate('2025-12-25')) AS clickhouse_includes
                
            FROM bronze.bpm_act_hi_taskinst t
            LEFT JOIN silver.mv_varinst_pivoted v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
            WHERE v.varinst_plant = 'WJ2'
              AND v.varinst_factory = 'NBU' 
              AND v.varinst_lineName = 'E5'
              AND (
                  toDate(t.START_TIME_) = '2025-12-25'
                  OR toDate(t.CLAIM_TIME_) = '2025-12-25'
                  OR toDate(t.END_TIME_) = '2025-12-25'
              )
        )
        SELECT 
            task_id,
            START_TIME_,
            CLAIM_TIME_,
            END_TIME_,
            mssql_should_include,
            clickhouse_includes,
            expanded_dates,
            CASE 
                WHEN mssql_should_include = clickhouse_includes THEN '✅ 一致'
                ELSE '❌ 不一致'
            END AS consistency_check
        FROM time_expansion_check
        ORDER BY task_id
        """
        
        result = client.query(query_time_expansion)
        
        if result.result_rows:
            print(f"找到 {len(result.result_rows)} 個任務")
            for row in result.result_rows:
                task_id, start_time, claim_time, end_time, mssql_include, ch_include, expanded_dates, consistency = row
                print(f"Task: {task_id}")
                print(f"  START: {start_time}, CLAIM: {claim_time}, END: {end_time}")
                print(f"  MSSQL 應包含: {mssql_include}, ClickHouse 包含: {ch_include}")
                print(f"  展開日期: {expanded_dates}")
                print(f"  一致性: {consistency}")
                print()
        else:
            print("未找到符合條件的任務")
        
        # 2. 檢查 Silver 層實際資料
        print("\n2. 檢查 Silver 層實際統計資料")
        print("-" * 50)
        
        query_silver_stats = """
        SELECT 
            task_create_date,
            vx_type,
            plant,
            factory,
            line,
            COUNT(*) AS task_count,
            countIf(task_status = 'TODO') AS todo_count,
            countIf(task_status = 'DOING') AS doing_count,
            countIf(task_status = 'DONE') AS done_count
        FROM silver.mv_fact_task_vx_attribution_mdm
        WHERE plant = 'WJ2'
          AND factory = 'NBU'
          AND line = 'E5'
          AND task_create_date BETWEEN '2025-12-25' AND '2025-12-31'
          AND is_excluded = 0
        GROUP BY task_create_date, vx_type, plant, factory, line
        ORDER BY task_create_date, vx_type
        """
        
        result = client.query(query_silver_stats)
        
        if result.result_rows:
            print("Silver 層統計結果：")
            total_tasks = 0
            for row in result.result_rows:
                date, vx, plant, factory, line, count, todo, doing, done = row
                total_tasks += count
                print(f"  {date} {vx}: 總計 {count} (TODO: {todo}, DOING: {doing}, DONE: {done})")
            print(f"\n總任務數: {total_tasks}")
        else:
            print("Silver 層無資料")
        
        # 3. 檢查時間模式分析
        print("\n3. 任務時間模式分析")
        print("-" * 50)
        
        query_time_patterns = """
        WITH task_patterns AS (
            SELECT 
                t.ID_ AS task_id,
                t.START_TIME_,
                t.CLAIM_TIME_,
                t.END_TIME_,
                
                CASE 
                    WHEN t.CLAIM_TIME_ IS NULL THEN 'NO_CLAIM'
                    WHEN abs(dateDiff('second', t.CLAIM_TIME_, t.END_TIME_)) <= 1 THEN 'AUTO_CLAIM_COMPLETE'
                    WHEN t.CLAIM_TIME_ > t.START_TIME_ THEN 'MANUAL_CLAIM'
                    ELSE 'OTHER'
                END AS pattern,
                
                length(arrayDistinct(arrayFilter(x -> x IS NOT NULL, [
                    toDate(t.START_TIME_),
                    toDate(t.CLAIM_TIME_),
                    toDate(t.END_TIME_)
                ]))) AS unique_dates
                
            FROM bronze.bpm_act_hi_taskinst t
            LEFT JOIN silver.mv_varinst_pivoted v ON t.PROC_INST_ID_ = v.PROC_INST_ID_
            WHERE v.varinst_plant = 'WJ2'
              AND v.varinst_factory = 'NBU' 
              AND v.varinst_lineName = 'E5'
              AND toDate(t.START_TIME_) >= '2025-12-20'
        )
        SELECT 
            pattern,
            COUNT(*) AS task_count,
            AVG(unique_dates) AS avg_unique_dates,
            any(task_id) AS sample_task
        FROM task_patterns
        GROUP BY pattern
        ORDER BY task_count DESC
        """
        
        result = client.query(query_time_patterns)
        
        if result.result_rows:
            print("時間模式分析：")
            for row in result.result_rows:
                pattern, count, avg_dates, sample = row
                print(f"  {pattern}: {count} 個任務, 平均 {avg_dates:.1f} 個唯一日期, 範例: {sample}")
        
        # 4. 與 MSSQL 參考結果比較
        print("\n4. 與 MSSQL 參考結果比較")
        print("-" * 50)
        
        mssql_reference = [
            "1178d911-e0aa-11f0-8766-badd3bc212ac - V3_5_3_9_1 - DOING",
            "a83fa1af-e124-11f0-8766-badd3bc212ac - V3_5_1_10_1 - TODO", 
            "a8c8a825-e124-11f0-8766-badd3bc212ac - V3_5_1_10_1 - TODO",
            "a9607bab-e124-11f0-8766-badd3bc212ac - V3_5_1_10_1 - TODO",
            "dc9cab8e-e155-11f0-8766-badd3bc212ac - V3_5_1_0_1 - TODO"
        ]
        
        print("MSSQL 參考結果（5個任務）：")
        for ref in mssql_reference:
            print(f"  {ref}")
        
        # 檢查 ClickHouse 是否有相同的任務
        query_clickhouse_match = """
        SELECT 
            original_task_id,
            task_definition_key,
            task_status,
            task_create_date
        FROM silver.mv_fact_task_vx_attribution_mdm
        WHERE plant = 'WJ2'
          AND factory = 'NBU'
          AND line = 'E5'
          AND task_create_date = '2025-12-25'
          AND is_excluded = 0
        ORDER BY original_task_id
        """
        
        result = client.query(query_clickhouse_match)
        
        print(f"\nClickHouse 對應結果（{len(result.result_rows)}個任務）：")
        if result.result_rows:
            for row in result.result_rows:
                task_id, task_key, status, date = row
                print(f"  {task_id} - {task_key} - {status} - {date}")
        
        print("\n=== 驗證完成 ===")
        
    except Exception as e:
        print(f"錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()