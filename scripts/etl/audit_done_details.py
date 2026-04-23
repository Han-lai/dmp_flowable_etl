# -*- coding: utf-8 -*-
"""
DMP Flowable: Task Audit Tool (V7 - Full Status)
Purpose: Extract detailed task list for tasks on a specific snapshot date.
Mirrors Gold milestone logic: todo/doing/done/all status filtering.
Supports 5-level hierarchy: Region, Plant, Factory, Line, VX Type.
"""

import clickhouse_connect
import argparse
import pandas as pd
from datetime import datetime
import os

# ClickHouse Configuration
CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', 'REDACTED_IP'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8123')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', 'REDACTED_PASSWORD'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}

def get_client():
    return clickhouse_connect.get_client(**CH_CONFIG)

def audit_done_details(date, region, plant, factory, line, vx_type, status='done'):
    client = get_client()
    
    # 建立過濾器
    filters = []
    if region: filters.append(f"region = '{region}'")
    if plant: filters.append(f"plant = '{plant}'")
    if factory: filters.append(f"factory = '{factory}'")
    if line: filters.append(f"line = '{line}'")
    if vx_type: filters.append(f"vx_type = '{vx_type}'")
    
    filter_sql = " AND ".join(filters)
    if filter_sql:
        filter_sql = "AND " + filter_sql
    
    status_label_map = {'done': 'DONE', 'todo': 'TODO', 'doing': 'DOING', 'all': 'ALL'}
    status_label = status_label_map.get(status, 'DONE')
    print(f"\n{'='*100}")
    print(f" AUDIT REPORT: {status_label} Tasks on snapshot date {date}")
    print(f" Hierarchy: {region} / {plant} / {factory} / {line} | VX: {vx_type}")
    print(f"{'='*100}\n")

    # Build date filter mirroring Gold milestone ARRAY JOIN logic exactly.
    # Silver stores NULL (via NULLIF) for missing claim/end dates — not epoch.
    # Gold only counts a task's state on the dates in its lifecycle [start, claim, end].
    if status == 'done':
        # Matches Gold: task_end_date IS NOT NULL AND snapshot_date >= task_end_date
        # Since tasks ending before snapshot_date cannot touch snapshot_date via start/claim,
        # this reduces to: task_end_date = snapshot_date
        date_filter = (
            f"AND task_end_date IS NOT NULL\n"
            f"      AND task_end_date = '{date}'"
        )
    elif status == 'todo':
        # Matches Gold: snapshot_date < COALESCE(task_claim_date, task_end_date, tomorrow)
        # Task must start on snapshot_date (only start is in ARRAY on a not-yet-claimed task)
        date_filter = (
            f"AND task_start_date = '{date}'\n"
            f"      AND COALESCE(task_claim_date, task_end_date, toDate('9999-12-31')) > '{date}'"
        )
    elif status == 'doing':
        # Matches Gold: claim IS NOT NULL AND snapshot >= claim AND (end IS NULL OR snapshot < end)
        # Task must touch snapshot_date via start or claim date
        date_filter = (
            f"AND (task_start_date = '{date}' OR task_claim_date = '{date}')\n"
            f"      AND task_claim_date IS NOT NULL AND task_claim_date <= '{date}'\n"
            f"      AND (task_end_date IS NULL OR task_end_date > '{date}')"
        )
    else:  # all
        # Union: any task whose lifecycle touches snapshot_date (mirrors ARRAY JOIN source set)
        date_filter = (
            f"AND (task_start_date = '{date}' OR task_claim_date = '{date}' OR task_end_date = '{date}')"
        )

    # 2. Detailed Query
    detail_sql = f"""
    SELECT
        task_id,
        task_start_time,
        task_claim_time,
        task_end_time,
        task_start_date,
        task_claim_date,
        task_end_date,
        task_primary_date,
        task_create_date,
        task_status,
        vx_type,
        region,
        plant,
        factory,
        line,
        region_source,
        plant_source,
        factory_source,
        line_source,
        is_excluded,
        exclude_reason,
        assignee_code,
        assignee_name,
        task_definition_key,
        task_name,
        mo_number,
        proc_inst_id,
        _mview_update_time
    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0
      {filter_sql}
      {date_filter}
    ORDER BY task_end_time DESC, task_start_time DESC
    """

    res_detail = client.query(detail_sql)
    if not res_detail.result_rows:
        print(f"No tasks found for this criteria.")
        return

    df = pd.DataFrame(res_detail.result_rows, columns=[
        'task_id', 'task_start_time', 'task_claim_time', 'task_end_time',
        'task_start_date', 'task_claim_date', 'task_end_date', 'task_primary_date',
        'task_create_date', 'task_status', 'vx_type',
        'region', 'plant', 'factory', 'line',
        'region_source', 'plant_source', 'factory_source', 'line_source',
        'is_excluded', 'exclude_reason',
        'assignee_code', 'assignee_name',
        'task_definition_key', 'task_name', 'mo_number', 'proc_inst_id',
        '_mview_update_time'
    ])
    
    print(f"Total {status_label} Tasks found: {len(df)}")
    
    # Show first 20 tasks
    print("\nDetailed List (Top 20 with Raw ClickHouse Timestamps):")
    print(df.head(20).to_string(index=False))
    
    # Save to CSV for the user
    output_prefix = f"{region}_{plant}_{factory}_{line}".replace("None", "X")
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scratch")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"audit_{status}_{output_prefix}_{date}.csv")
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\nFull details saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Audit DONE details from ClickHouse (Simplified List).")
    parser.add_argument("--date", type=str, required=True, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--region", type=str, help="Region (e.g., CNE, CNS)")
    parser.add_argument("--plant", type=str, help="Plant (e.g., WJ2, DG3)")
    parser.add_argument("--factory", type=str, help="Factory (e.g., NBU, SMT)")
    parser.add_argument("--line", type=str, help="Line (e.g., E5, ST02)")
    parser.add_argument("--vx", type=str, help="VX Type (V3, etc.)")
    parser.add_argument("--status", type=str, default='done', choices=['done', 'todo', 'doing', 'all'],
                        help="Filter by task status on snapshot date: 'done' (default), 'todo', 'doing', 'all'")

    args = parser.parse_args()

    try:
        audit_done_details(args.date, args.region, args.plant, args.factory, args.line, args.vx, args.status)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
