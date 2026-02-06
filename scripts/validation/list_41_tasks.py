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
    base_filters = "region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3' AND is_excluded = 0"
    date = '2025-12-25'
    win_sql = f"(task_start_date >= subtractDays(toDate('{date}'), 6) OR (task_claim_date IS NOT NULL AND task_claim_date >= subtractDays(toDate('{date}'), 6)))"
    
    q = f"""
    SELECT task_id, task_name, task_definition_key, task_start_date, task_claim_date, task_end_date 
    FROM silver.mv_fact_task_vx FINAL 
    WHERE {base_filters} AND {win_sql} AND task_start_date <= '{date}' AND (task_end_date IS NULL OR task_end_date > '{date}')
    """
    res = client.query(q)
    print(f"Total count: {len(res.result_rows)}")
    print(f"{'ID':<10} | {'Name':<40} | {'Key':<20} | {'Start':<10} | {'Claim':<10} | {'End':<10}")
    print("-" * 110)
    for r in res.result_rows:
        print(f"{r[0][:8]:<10} | {r[1][:40]:<40} | {r[2]:<20} | {str(r[3]):<10} | {str(r[4]):<10} | {str(r[5]):<10}")

if __name__ == "__main__":
    main()
