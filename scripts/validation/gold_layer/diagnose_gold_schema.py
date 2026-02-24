import clickhouse_connect
import pandas as pd

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

PLANT = 'DG3'
FACTORY = 'SMT'
LINE = 'ST02'

def get_gold_inner():
    r = client.query("SELECT name FROM system.tables WHERE database='gold' AND name LIKE '.inner_id.%' ORDER BY total_rows DESC LIMIT 1")
    if r.result_rows:
        return r.result_rows[0][0]
    return None

table = get_gold_inner()
if not table:
    print("No Gold inner table found.")
else:
    print(f"Inspecting Gold Inner Table: {table}")
    
    # 1. Get Columns via LIMIT 1
    try:
        r = client.query(f"SELECT * FROM gold.`{table}` LIMIT 1")
        print(f"Columns: {r.column_names}")
        cols = r.column_names
    except Exception as e:
        print(f"Error fetching sample: {e}")
        cols = []

    # 2. Construct Query
    if 'plant_code' in cols:
        p_col = 'plant_code'
    else:
        p_col = 'plant'
        
    if 'factory_code' in cols:
        f_col = 'factory_code'
    else:
        f_col = 'factory'
        
    # Find line column
    l_col = None
    for c in ['line_code', 'line_name', 'line']:
        if c in cols:
            l_col = c
            break
            
    if p_col and f_col and l_col:
        print(f"Querying with: {p_col}, {f_col}, {l_col}")
        query = f"""
            SELECT count()
            FROM gold.`{table}`
            WHERE {p_col} = '{PLANT}'
              AND {f_col} = '{FACTORY}'
              AND {l_col} = '{LINE}'
        """
        try:
            r = client.query(query)
            print(f"Gold rows for {PLANT}/{FACTORY}/{LINE}: {r.result_rows[0][0]}")
        except Exception as e:
            print(f"Error querying: {e}")
    else:
         print(f"Could not map columns. {cols}")
