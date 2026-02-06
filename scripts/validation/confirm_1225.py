import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    base_filters = "region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3' AND is_excluded = 0"
    date = '2025-12-25'
    
    # Using 6-day window (subtract 5 days)
    win_sql = f"(task_start_date >= subtractDays(toDate('{date}'), 5) OR (task_claim_date IS NOT NULL AND task_claim_date >= subtractDays(toDate('{date}'), 5)))"
    
    q = f"""
    SELECT t.task_id, t.task_name, t.task_definition_key, raw.DELETE_REASON_, t.task_status, t.task_start_date, t.task_end_date
    FROM silver.mv_fact_task_vx t
    LEFT JOIN bronze.bpm_act_hi_taskinst raw ON t.task_id = raw.ID_
    WHERE {base_filters} AND {win_sql} AND t.task_start_date <= '{date}' AND (t.task_end_date IS NULL OR t.task_end_date > '{date}')
    """
    
    res = client.query(q)
    print(f"Total found: {len(res.result_rows)}")
    print(f"{'ID':<10} | {'Name':<30} | {'Key':<30} | {'Status':<10} | {'DelReason':<10}")
    print("-" * 100)
    for row in res.result_rows:
        tid = row[0][:8]
        name = row[1][:30]
        key = row[2][:30]
        del_reason = str(row[3]) if row[3] else "None"
        status = row[4]
        
        is_suspicious = del_reason != "None" or "Notify" in name or "Dummy" in name
        marker = " [!] " if is_suspicious else "     "
        print(f"{tid:<10} | {name:<30} | {key:<30} | {status:<10} | {del_reason:<10}{marker}")

if __name__ == "__main__":
    main()
