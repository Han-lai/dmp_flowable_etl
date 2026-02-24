import clickhouse_connect
import pandas as pd

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

PLANT = 'DG3'
FACTORY = 'SMT'
LINE = 'ST02'

def get_inner_table(db, mv_name):
    # Find the inner table for a given MV
    # This is heuristic: usually .inner_id.{uuid}
    # We can also check system.tables for dependencies, but let's just grab the largest ReplacingMergeTree in the DB
    # or match the UUID if we can find it.
    
    # Actually, we can use `system.tables` to find tables with name starting with `.inner_id.`
    # and sort by rows to find the big ones.
    
    print(f"Finding inner table for {db}.{mv_name}...")
    r = client.query(f"SELECT name, total_rows FROM system.tables WHERE database='{db}' AND name LIKE '.inner_id.%' ORDER BY total_rows DESC")
    if not r.result_rows:
        print("No inner tables found.")
        return None
        
    # Just return the largest one for now (likely the main data table)
    # Or print all
    vals = []
    for row in r.result_rows:
        print(f"  Found inner table: {row[0]} ({row[1]} rows)")
        vals.append(row[0])
    return vals

def query_inner(db, table, label):
    print(f"\nQuerying {db}.{table} ({label})...")
    try:
        # Check explicit columns if known, or specific ones
        # For Gold RMV: snapshot_date, plant, factory, line, vx_type...
        if 'rmv' in label or 'gold' in db:
            cols = "plant, factory, line, vx_type"
        else:
            cols = "plant, factory, line, vx_type" # Silver likely has similar if it's fact_task_vx

        # Try to guess columns by DESCRIBE
        try:
            r_desc = client.query(f"DESCRIBE {db}.`{table}`")
            avail_cols = [r[0] for r in r_desc.result_rows]
            print(f"  Columns: {avail_cols[:5]}...")
        except:
            print("  Could not describe table.")
            avail_cols = []

        # Construct query
        if 'plant' in avail_cols:
             query = f"""
                SELECT plant, factory, line, count() 
                FROM {db}.`{table}`
                WHERE plant='{PLANT}'
                GROUP BY plant, factory, line
             """
        elif 'plant_code' in avail_cols:
             query = f"""
                SELECT plant_code, factory_code, line_code, count() 
                FROM {db}.`{table}`
                WHERE plant_code='{PLANT}'
                GROUP BY plant_code, factory_code, line_code
             """
        else:
             print("  'plant' or 'plant_code' column not found, skipping specific query.")
             return

        r = client.query(query)
        if not r.result_rows:
             print(f"  ❌ No data for {PLANT} in {table}")
        else:
             print(f"  ✅ Found data for {PLANT}:")
             for row in r.result_rows:
                 print(f"    {row}")
             
    except Exception as e:
        print(f"  Error querying {table}: {e}")

# Silver check
silver_inners = get_inner_table('silver', 'mv_fact_task_vx')
if silver_inners:
    # Try the largest one
    query_inner('silver', silver_inners[0], 'Silver Fact')

# Gold check
gold_inners = get_inner_table('gold', 'rmv_l5_task_completion')
if gold_inners:
    # Try the largest one
    query_inner('gold', gold_inners[0], 'Gold RMV')
