#!/usr/bin/env python3
"""
查詢 L5 任務數 - 通用指標
從 bronze.common_flowable_task_stats 計算 L5 任務數

篩選條件：
- Plant = 'WJ2'
- Factory = 'NBU'  
- LineName = 'E5'
- 日期 = 2025-12-25
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
    print("L5 任務數查詢 - 通用指標")
    print("條件: CNE WJ2 NBU E5 | 日期: 2025-12-25")
    print("=" * 80)
    
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    # 查詢參數
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    target_date = '2025-12-25'
    
    # 時間範圍條件 (與 L5_task_sample.sql 一致)
    time_filter = f"""
        (
            toDate(TaskCreateTime) = '{target_date}'
            OR toDate(TaskClaimTime) = '{target_date}'
            OR toDate(TaskEndTime) = '{target_date}'
        )
    """
    
    # 基本篩選條件
    base_filter = f"""
        Plant = '{plant}'
        AND Factory = '{factory}'
        AND Line = '{line}'
        AND {time_filter}
    """
    
    # 1. 查詢可用欄位
    print("\n1. 表結構確認:")
    try:
        cols = client.query("""
            SELECT name, type 
            FROM system.columns 
            WHERE database = 'bronze' AND table = 'common_flowable_task_stats'
            ORDER BY position
        """)
        for row in cols.result_rows[:15]:  # 只顯示前15個欄位
            print(f"   {row[0]}: {row[1]}")
        print(f"   ... 共 {len(cols.result_rows)} 個欄位")
    except Exception as e:
        print(f"   錯誤: {e}")
    
    # 2. 總任務數 (不含 bypass)
    print("\n2. L5 任務數統計 (TaskBypass = 'N'):")
    
    # 2.1 總數
    total_sql = f"""
        SELECT count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE {base_filter}
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
    """
    try:
        total = client.command(total_sql)
        print(f"   Total Task (不含 bypass): {total:,}")
    except Exception as e:
        print(f"   錯誤: {e}")
    
    # 2.2 按 TaskStatus 分布
    print("\n3. TaskStatus 分布:")
    status_sql = f"""
        SELECT 
            TaskStatus,
            count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE {base_filter}
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
        GROUP BY TaskStatus
        ORDER BY cnt DESC
    """
    try:
        result = client.query(status_sql)
        total_non_bypass = 0
        for row in result.result_rows:
            print(f"   {row[0]}: {row[1]:,}")
            total_non_bypass += row[1]
        print(f"   ---")
        print(f"   合計: {total_non_bypass:,}")
    except Exception as e:
        print(f"   錯誤: {e}")
    
    # 2.3 排除 E/C 開頭的任務 (根據 metric_definitions.md)
    print("\n4. 排除 E/C 開頭任務後的統計:")
    excluded_sql = f"""
        SELECT 
            TaskStatus,
            count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE {base_filter}
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
        AND TaskDefinitionKey NOT LIKE 'E%'
        AND TaskDefinitionKey NOT LIKE 'C%'
        GROUP BY TaskStatus
        ORDER BY cnt DESC
    """
    try:
        result = client.query(excluded_sql)
        total_excluded = 0
        done_count = 0
        doing_count = 0
        todo_count = 0
        
        for row in result.result_rows:
            status = row[0]
            cnt = row[1]
            print(f"   {status}: {cnt:,}")
            total_excluded += cnt
            if status.upper() == 'DONE':
                done_count = cnt
            elif status.upper() == 'DOING':
                doing_count = cnt
            elif status.upper() == 'TODO':
                todo_count = cnt
        
        print(f"   ---")
        print(f"   合計: {total_excluded:,}")
        
        # 計算百分比
        if total_excluded > 0:
            print(f"\n   📊 百分比:")
            print(f"   Done: {done_count:,} ({done_count/total_excluded*100:.1f}%)")
            print(f"   Doing: {doing_count:,} ({doing_count/total_excluded*100:.1f}%)")
            print(f"   Todo: {todo_count:,} ({todo_count/total_excluded*100:.1f}%)")
            print(f"   Doing+Done: {doing_count+done_count:,} ({(doing_count+done_count)/total_excluded*100:.1f}%)")
    except Exception as e:
        print(f"   錯誤: {e}")
    
    # 3. 按 Vx 類型分組
    print("\n5. 按 Vx 類型分組 (前2碼):")
    vx_sql = f"""
        SELECT 
            substring(TaskDefinitionKey, 1, 2) as vx_type,
            TaskStatus,
            count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE {base_filter}
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
        AND TaskDefinitionKey NOT LIKE 'E%'
        AND TaskDefinitionKey NOT LIKE 'C%'
        GROUP BY vx_type, TaskStatus
        ORDER BY vx_type, TaskStatus
    """
    try:
        result = client.query(vx_sql)
        current_vx = None
        vx_total = 0
        for row in result.result_rows:
            vx = row[0]
            status = row[1]
            cnt = row[2]
            if vx != current_vx:
                if current_vx is not None:
                    print(f"      小計: {vx_total}")
                print(f"   [{vx}]")
                current_vx = vx
                vx_total = 0
            print(f"      {status}: {cnt:,}")
            vx_total += cnt
        if current_vx is not None:
            print(f"      小計: {vx_total}")
    except Exception as e:
        print(f"   錯誤: {e}")
    
    # 4. 查詢 bypass 的任務數
    print("\n6. Bypass 任務數 (TaskBypass = 'Y'):")
    bypass_sql = f"""
        SELECT count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE {base_filter}
        AND TaskBypass = 'Y'
    """
    try:
        bypass_count = client.command(bypass_sql)
        print(f"   Bypass 任務: {bypass_count:,}")
    except Exception as e:
        print(f"   錯誤: {e}")
    
    # 5. 查詢樣本資料
    print("\n7. 樣本資料 (前5筆):")
    sample_sql = f"""
        SELECT 
            TaskId,
            TaskDefinitionKey,
            TaskName,
            TaskStatus,
            TaskBypass,
            TaskCreateTime,
            TaskEndTime
        FROM bronze.common_flowable_task_stats FINAL
        WHERE {base_filter}
        AND (TaskBypass = 'N' OR TaskBypass IS NULL)
        LIMIT 5
    """
    try:
        result = client.query(sample_sql)
        for i, row in enumerate(result.result_rows, 1):
            print(f"   {i}. {row[1]} | {row[3]} | Bypass={row[4]} | {row[5]}")
    except Exception as e:
        print(f"   錯誤: {e}")
    
    print("\n" + "=" * 80)
    client.close()

if __name__ == "__main__":
    main()
