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
import sys

# ClickHouse Configuration
CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', 'localhost'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8123')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', '<CLICKHOUSE_PASSWORD>'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}

def _validate_date(value: str):
    """確認日期為 YYYY-MM-DD 格式，避免靜默回傳 0 筆。"""
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        print(f"Error: --date must be YYYY-MM-DD, got: {value!r}")
        sys.exit(1)

def get_client():
    return clickhouse_connect.get_client(**CH_CONFIG)

def audit_done_details(date, region, plant, factory, line, vx_type, status='done'):
    _validate_date(date)

    client = get_client()

    # Build WHERE conditions using parameterized queries to prevent SQL injection.
    conditions = ["is_excluded = 0"]
    params = {'p_date': date}

    if region:
        conditions.append("region = {p_region:String}")
        params['p_region'] = region
    if plant:
        conditions.append("plant = {p_plant:String}")
        params['p_plant'] = plant
    if factory:
        conditions.append("factory = {p_factory:String}")
        params['p_factory'] = factory
    if line:
        conditions.append("line = {p_line:String}")
        params['p_line'] = line
    if vx_type:
        conditions.append("vx_type = {p_vx:String}")
        params['p_vx'] = vx_type

    # Build date conditions mirroring Gold milestone V4 Cohort logic exactly.
    # Silver stores NULL (via NULLIF) for missing claim/end dates — not epoch.
    if status == 'done':
        conditions.append("task_start_date = {p_date:Date}")
        conditions.append("task_end_date = {p_date:Date}")
    elif status == 'todo':
        conditions.append("task_start_date = {p_date:Date}")
        conditions.append("COALESCE(task_claim_date, toDate('1900-01-01')) != {p_date:Date}")
        conditions.append("(task_end_date IS NULL OR task_end_date != {p_date:Date})")
    elif status == 'doing':
        conditions.append("task_start_date = {p_date:Date}")
        conditions.append("task_claim_date = {p_date:Date}")
        conditions.append("(task_end_date IS NULL OR task_end_date != {p_date:Date})")
    else:  # all
        conditions.append("task_start_date = {p_date:Date}")

    status_label_map = {'done': 'DONE', 'todo': 'TODO', 'doing': 'DOING', 'all': 'ALL'}
    status_label = status_label_map.get(status, 'DONE')
    print(f"\n{'='*100}")
    print(f" AUDIT REPORT: {status_label} Tasks on snapshot date {date}")
    print(f" Hierarchy: {region} / {plant} / {factory} / {line} | VX: {vx_type}")
    print(f"{'='*100}\n")

    detail_sql = """
    SELECT *
    FROM silver.mv_fact_task_vx FINAL
    WHERE {}
    ORDER BY task_end_time DESC, task_start_time DESC
    """.format(" AND ".join(conditions))

    res_detail = client.query(detail_sql, parameters=params)
    if not res_detail.result_rows:
        print(f"No tasks found for this criteria.")
        return

    df = pd.DataFrame(res_detail.result_rows, columns=res_detail.column_names)
    
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
