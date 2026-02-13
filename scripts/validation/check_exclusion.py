import clickhouse_connect

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

PLANT = 'DG3'
FACTORY = 'SMT'
LINE = 'ST02'

print(f"Checking is_excluded for {PLANT}/{FACTORY}/{LINE} in silver.mv_fact_task_vx...")

try:
    # Dump Silver DDL
    r_ddl = client.query("SHOW CREATE TABLE silver.mv_fact_task_vx")
    with open('silver_ddl.sql', 'w', encoding='utf-8') as f:
        f.write(r_ddl.result_rows[0][0])
    print("Silver DDL written to silver_ddl.sql")

    # Check Exclusion
    table = "silver.`.inner_id.86c879ce-df98-4980-b955-d6a4225c89a5`"
    
    query = f"""
    SELECT is_excluded, count() 
    FROM {table}
    WHERE plant = '{PLANT}' 
      AND factory = '{FACTORY}' 
      AND line = '{LINE}'
    GROUP BY is_excluded
    """
    
    r = client.query(query)
    if not r.result_rows:
        print("No rows found.")
    else:
        print("is_excluded distribution:")
        for row in r.result_rows:
            print(f"  is_excluded={row[0]}: {row[1]} rows")

except Exception as e:
    print(f"Error: {e}")
