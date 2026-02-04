import clickhouse_connect

def main():
    client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')
    q = """
        SELECT task_id, task_definition_key, task_end_date, vx_type, mo_number 
        FROM silver.mv_fact_task_vx FINAL 
        WHERE (task_start_date = '2025-12-25' OR task_claim_date = '2025-12-25' OR task_end_date = '2025-12-25') 
          AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' 
          AND vx_type = 'V1'
          AND is_excluded = 0
    """
    rows = client.query(q).result_rows
    print(f"Found {len(rows)} tasks currently marked as V1 for 12/25 E5:")
    for r in rows:
        print(f"ID: {r[0]}, Key: {r[1]}, EndDate: {r[2]}, Vx: {r[3]}, MO: {r[4]}")

if __name__ == "__main__":
    main()
