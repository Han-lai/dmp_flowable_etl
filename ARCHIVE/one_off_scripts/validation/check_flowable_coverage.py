#!/usr/bin/env python3
"""
檢查 FlowableTaskStats 欄位覆蓋率分析
1. MoNumber 欄位覆蓋率
2. NPE 判別欄位可用性
"""

import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("=" * 80)
    print("1. MoNumber 欄位覆蓋率分析")
    print("=" * 80)
    
    # 總筆數
    total = client.command("SELECT count() FROM bronze.common_flowable_task_stats FINAL")
    print(f"總筆數: {total:,}")
    
    # MoNumber 非空筆數
    non_null = client.command("""
        SELECT count() 
        FROM bronze.common_flowable_task_stats FINAL
        WHERE MoNumber IS NOT NULL AND MoNumber != ''
    """)
    print(f"MoNumber 有值: {non_null:,} ({non_null/total*100:.2f}%)")
    print(f"MoNumber 空值: {total-non_null:,} ({(total-non_null)/total*100:.2f}%)")
    
    # 按 Vx 類型分析 MoNumber 覆蓋率
    print("\n按 Vx 類型的 MoNumber 覆蓋率:")
    result = client.query("""
        SELECT 
            substring(TaskDefinitionKey, 1, 2) as vx_type,
            count() as total,
            countIf(MoNumber IS NOT NULL AND MoNumber != '') as has_mo,
            round(countIf(MoNumber IS NOT NULL AND MoNumber != '') * 100.0 / count(), 2) as pct
        FROM bronze.common_flowable_task_stats FINAL
        GROUP BY vx_type
        ORDER BY total DESC
        LIMIT 10
    """)
    print(f"  {'Vx':^6} | {'Total':>12} | {'有MoNumber':>12} | {'覆蓋率':>8}")
    print(f"  {'-'*6} | {'-'*12} | {'-'*12} | {'-'*8}")
    for row in result.result_rows:
        print(f"  {row[0]:^6} | {row[1]:>12,} | {row[2]:>12,} | {row[3]:>7.2f}%")
    
    print()
    print("=" * 80)
    print("2. NPE 判別欄位分析")
    print("=" * 80)
    
    # 檢查可能的 NPE 相關欄位
    cols = client.query("""
        SELECT name, type 
        FROM system.columns 
        WHERE database = 'bronze' AND table = 'common_flowable_task_stats'
        AND (lower(name) LIKE '%npe%' OR lower(name) LIKE '%factory%' 
             OR lower(name) LIKE '%business%' OR lower(name) LIKE '%process%')
        ORDER BY position
    """)
    print("\n可能的 NPE 相關欄位:")
    for row in cols.result_rows:
        print(f"  {row[0]}: {row[1]}")
    
    # 檢查 Factory 欄位的值分布
    print("\nFactory 欄位值分布 (Top 15):")
    result = client.query("""
        SELECT Factory, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE Factory IS NOT NULL AND Factory != ''
        GROUP BY Factory
        ORDER BY cnt DESC
        LIMIT 15
    """)
    for row in result.result_rows:
        npe_mark = " <-- 包含NPE" if "NPE" in str(row[0]).upper() else ""
        print(f"  {row[0]}: {row[1]:,}{npe_mark}")
    
    # 檢查是否有包含 NPE 的 Factory
    npe_count = client.command("""
        SELECT count() 
        FROM bronze.common_flowable_task_stats FINAL
        WHERE Factory LIKE '%NPE%'
    """)
    print(f"\nFactory 包含 NPE 的筆數: {npe_count:,}")
    
    # 檢查 ProcessTeam 是否包含 NPE
    print("\nProcessTeam 欄位中包含 NPE 的情況:")
    result = client.query("""
        SELECT ProcessTeam, count() as cnt
        FROM bronze.common_flowable_task_stats FINAL
        WHERE ProcessTeam LIKE '%NPE%'
        GROUP BY ProcessTeam
        ORDER BY cnt DESC
        LIMIT 10
    """)
    if result.result_rows:
        for row in result.result_rows:
            print(f"  {row[0]}: {row[1]:,}")
    else:
        print("  (無資料)")
    
    # 檢查所有可用欄位
    print("\n" + "=" * 80)
    print("3. FlowableTaskStats 所有欄位一覽")
    print("=" * 80)
    cols = client.query("""
        SELECT name, type 
        FROM system.columns 
        WHERE database = 'bronze' AND table = 'common_flowable_task_stats'
        ORDER BY position
    """)
    print("\n所有欄位:")
    for i, row in enumerate(cols.result_rows, 1):
        print(f"  {i:2d}. {row[0]}: {row[1]}")
    
    client.close()
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
