#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClickHouse MView 問題診斷腳本
"""

import clickhouse_connect

CH_HOST = '10.136.218.207'
CH_PORT = 8121
CH_USER = 'default'
CH_PASSWORD = 'default'

def get_connection():
    return clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD
    )

def main():
    print("=" * 80)
    print("ClickHouse MView Problem Diagnosis")
    print("=" * 80)
    print()
    
    client = get_connection()
    
    # 1. Check MView DDL
    print("(1) Check mv_fact_task_vx_attribution DDL")
    print("-" * 80)
    
    sql = "SHOW CREATE TABLE silver.mv_fact_task_vx_attribution"
    result = client.query(sql)
    if result.result_rows:
        ddl = result.result_rows[0][0]
        print(ddl[:2000])
        print("\n... (DDL truncated)")
        
        print("\nKey Features Check:")
        print(f"  - Contains LIKE '315%': {'LIKE' in ddl and '315%' in ddl}")
        print(f"  - Contains IN ('3152600035': {'IN' in ddl and '3152600035' in ddl}")
        print(f"  - Contains varinst_name: {'varinst_name' in ddl}")
        print(f"  - Contains mv_varinst_pivoted: {'mv_varinst_pivoted' in ddl}")
    
    # 2. Check source table data
    print("\n" + "=" * 80)
    print("(2) Check Source Table Data")
    print("-" * 80)
    
    sql = """
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT toDate(TaskCreateTime)) as date_count,
        MIN(toDate(TaskCreateTime)) as min_date,
        MAX(toDate(TaskCreateTime)) as max_date
    FROM bronze.common_flowable_task_stats
    """
    result = client.query(sql)
    if result.result_rows:
        total, date_count, min_date, max_date = result.result_rows[0]
        print(f"\nbronze.common_flowable_task_stats:")
        print(f"  - Total rows: {total}")
        print(f"  - Date range: {min_date} to {max_date}")
        print(f"  - Date count: {date_count}")
    
    sql = """
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT toDate(_mview_update_time)) as date_count,
        MIN(toDate(_mview_update_time)) as min_date,
        MAX(toDate(_mview_update_time)) as max_date
    FROM silver.mv_varinst_pivoted
    """
    result = client.query(sql)
    if result.result_rows:
        total, date_count, min_date, max_date = result.result_rows[0]
        print(f"\nsilver.mv_varinst_pivoted:")
        print(f"  - Total rows: {total}")
        print(f"  - Date range: {min_date} to {max_date}")
        print(f"  - Date count: {date_count}")
    
    # 3. Check POPULATE status
    print("\n" + "=" * 80)
    print("(3) Check MView POPULATE Status")
    print("-" * 80)
    
    sql = "SHOW CREATE TABLE silver.mv_fact_task_vx_attribution"
    result = client.query(sql)
    if result.result_rows:
        ddl = result.result_rows[0][0]
        has_populate = 'POPULATE' in ddl
        print(f"\nmv_fact_task_vx_attribution:")
        print(f"  - Has POPULATE: {has_populate}")
        if has_populate:
            print(f"    OK: MView should auto-populate on creation")
        else:
            print(f"    WARNING: MView needs manual population")
    
    # 4. Check inner tables
    print("\n" + "=" * 80)
    print("(4) Check MView Inner Tables")
    print("-" * 80)
    
    sql = """
    SELECT 
        database,
        name,
        engine
    FROM system.tables
    WHERE database = 'silver'
        AND name LIKE '.inner.mv_fact_task_vx_attribution%'
    """
    result = client.query(sql)
    if result.result_rows:
        print(f"\nFound {len(result.result_rows)} inner tables:")
        for db, name, engine in result.result_rows:
            print(f"  - {db}.{name} ({engine})")
            
            sql2 = f"SELECT COUNT(*) FROM {db}.{name}"
            result2 = client.query(sql2)
            if result2.result_rows:
                count = result2.result_rows[0][0]
                print(f"    Rows: {count}")
    else:
        print("\nWARNING: No inner tables found")
    
    # 5. Check REFRESH strategy
    print("\n" + "=" * 80)
    print("(5) Check MView REFRESH Strategy")
    print("-" * 80)
    
    sql = "SHOW CREATE TABLE silver.mv_fact_task_vx_attribution"
    result = client.query(sql)
    if result.result_rows:
        ddl = result.result_rows[0][0]
        has_refresh = 'REFRESH' in ddl
        print(f"\nmv_fact_task_vx_attribution:")
        print(f"  - Has REFRESH: {has_refresh}")
        if not has_refresh:
            print(f"    INFO: MView uses auto-update based on source table changes")
    
    # 6. Check 315% rule implementation
    print("\n" + "=" * 80)
    print("(6) Check 315% Rule Implementation")
    print("-" * 80)
    
    sql = "SHOW CREATE TABLE silver.mv_fact_task_vx_attribution"
    result = client.query(sql)
    if result.result_rows:
        ddl = result.result_rows[0][0]
        
        if "LIKE '315%'" in ddl:
            print("\nOK: Using new rule: LIKE '315%'")
        elif "IN ('3152600035'" in ddl:
            print("\nERROR: Using old rule: IN ('3152600035', '3152600036', '3152600037')")
        else:
            print("\nWARNING: Cannot determine 315% rule implementation")
    
    # 7. Check NPE logic
    print("\n" + "=" * 80)
    print("(7) Check NPE Logic")
    print("-" * 80)
    
    sql = "SHOW CREATE TABLE silver.mv_fact_task_vx_attribution"
    result = client.query(sql)
    if result.result_rows:
        ddl = result.result_rows[0][0]
        
        if "varinst_name LIKE '%NPE%'" in ddl:
            print("\nOK: Using new logic: varinst_name LIKE '%NPE%'")
        elif "BUSINESS_KEY_ LIKE '%NPE%'" in ddl:
            print("\nERROR: Using old logic: BUSINESS_KEY_ LIKE '%NPE%'")
        else:
            print("\nWARNING: Cannot determine NPE logic")
    
    print("\n" + "=" * 80)
    print("Diagnosis Complete")
    print("=" * 80)

if __name__ == '__main__':
    main()
