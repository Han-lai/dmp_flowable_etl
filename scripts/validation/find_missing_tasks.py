import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
    q = """
        SELECT task_id, task_definition_key, task_end_date, vx_type, is_excluded, exclude_reason 
        FROM silver.mv_fact_task_vx FINAL 
        WHERE (task_start_date = '2025-12-25' OR task_claim_date = '2025-12-25' OR task_end_date = '2025-12-25') 
          AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
    """
    rows = client.query(q).result_rows
    print(f"Total tasks found for 12/25 E5 (including excluded): {len(rows)}")
    for r in rows:
        if r[4] == 1:
            print(f"EXCLUDED - ID: {r[0]}, Key: {r[1]}, Reason: {r[5]}, Vx: {r[3]}")
    
if __name__ == "__main__":
    main()
