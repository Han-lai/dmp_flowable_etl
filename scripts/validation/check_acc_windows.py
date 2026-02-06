import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def check_gold():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    q = "SELECT acc_todo_doing FROM gold.rmv_l5_task_completion FINAL WHERE snapshot_date = '2025-12-25' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3'"
    res = client.query(q)
    if res.result_rows:
        print(f"Current Value in Gold Table for 12/25 V3: {res.result_rows[0][0]}")
    else:
        print("No row found in Gold Table for 12/25 V3")

def test_windows():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    base_filters = "region = 'CNE' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND vx_type = 'V3' AND is_excluded = 0"
    date = '2025-12-25'
    
    for days in [4, 5, 6, 7]:
        win_sql = f"(task_start_date >= subtractDays(toDate('{date}'), {days}) OR (task_claim_date IS NOT NULL AND task_claim_date >= subtractDays(toDate('{date}'), {days})))"
        q = f"SELECT count() FROM silver.mv_fact_task_vx FINAL WHERE {base_filters} AND {win_sql} AND task_start_date <= '{date}' AND (task_end_date IS NULL OR task_end_date > '{date}')"
        count = client.query(q).result_rows[0][0]
        print(f"subtractDays(..., {days}) -> ACC: {count}")

if __name__ == "__main__":
    print("--- Checking Gold Table ---")
    check_gold()
    print("\n--- Testing Windows in Silver Layer ---")
    test_windows()
