import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    filters = "region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3' AND is_excluded = 0"
    date = '2025-12-25'
    
    print(f"--- Isolating the 14 Stale Tasks for 12/25 ---")
    base_filters = "region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3' AND is_excluded = 0"
    date = '2025-12-25'
    win_sql = f"(task_start_date >= subtractDays(toDate('{date}'), 5) OR (task_claim_date IS NOT NULL AND task_claim_date >= subtractDays(toDate('{date}'), 5)))"
    
    # Stale = In window AND Pending on D AND NO EVENT on D
    # No event on D means: start != D AND claim != D AND end != D (since it is pending, end is already != D)
    q = f"""
    SELECT task_id, task_name, task_definition_key, task_start_date, task_claim_date, task_status, mo_number
    FROM silver.mv_fact_task_vx FINAL
    WHERE {base_filters} AND {win_sql} 
      AND task_start_date < '{date}' 
      AND (task_end_date IS NULL OR task_end_date > '{date}')
      AND (task_claim_date IS NULL OR task_claim_date != '{date}')
    ORDER BY task_start_date
    """
    res = client.query(q)
    print(f"Total found: {len(res.result_rows)}")
    print("| ID | Name | Key | Start | Status | MO |")
    print("|----|------|-----|-------|--------|----|")
    for row in res.result_rows:
        print(f"| {row[0][:8]} | {row[1]:15} | {row[2]:10} | {row[3]} | {row[5]} | {row[6]} |")

if __name__ == "__main__":
    main()
