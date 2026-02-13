import clickhouse_connect
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

CH_HOST = '10.136.218.207'
CH_PORT = 8121

PLANT = 'DG3'
FACTORY = 'SMT'
LINE = 'ST02'

def diagnose():
    client = clickhouse_connect.get_client(host=CH_HOST, port=CH_PORT, username='default', password='default')
    
    print("=" * 60)
    print(f"Diagnosing: {PLANT}/{FACTORY}/{LINE} in ClickHouse")
    print("=" * 60)

    # =========================================
    # Step 1: Bronze has data (confirmed: 244k DG3, 174k SMT)
    # =========================================
    print("\n【Step 1: Bronze - VARINST (已確認)】")
    print("  ✅ DG3 rows: 244,372 | SMT (DG3 procs): 174,608")

    # =========================================
    # Step 2: List Silver tables
    # =========================================
    print("\n【Step 2: Silver tables】")
    try:
        r = client.query("SHOW TABLES FROM silver")
        for row in r.result_rows:
            print(f"  - {row[0]}")
    except Exception as e:
        print(f"  Error: {e}")

    # =========================================
    # Step 3: List Gold tables
    # =========================================
    print("\n【Step 3: Gold tables】")
    try:
        r = client.query("SHOW TABLES FROM gold")
        for row in r.result_rows:
            print(f"  - {row[0]}")
    except Exception as e:
        print(f"  Error: {e}")

    # =========================================
    # Step 4: Check Silver MV for DG3/SMT
    # =========================================
    print("\n【Step 4: Silver mv_varinst_pivoted (DG3/SMT)】")
    try:
        r = client.query("""
            SELECT count() FROM silver.mv_varinst_pivoted
            WHERE varinst_plant = 'DG3' AND varinst_factory = 'SMT'
        """)
        print(f"  Count: {r.result_rows[0][0]}")
    except Exception as e:
        print(f"  Error: {e}")

    # =========================================
    # Step 5: Check Silver Fact Table
    # =========================================
    print("\n【Step 5: Silver mv_fact_task_vx (DG3/SMT/ST02)】")
    try:
        # Assuming mv_fact_task_vx has joinable columns or direct columns. 
        # Usually it's joined with dimensions. Let's check raw count first if possible or check columns.
        # But based on name it likely has vx_type.
        # Let's try querying it with standard columns first
        r = client.query(f"""
            SELECT count() FROM silver.mv_fact_task_vx
            WHERE plant = '{PLANT}' AND factory = '{FACTORY}' AND line = '{LINE}'
        """)
        print(f"  Rows in silver.mv_fact_task_vx: {r.result_rows[0][0]}")
    except Exception as e:
        print(f"  Error querying silver.mv_fact_task_vx directly: {e}")
        # Fallback: List columns to understand schema
        try:
            r = client.query("DESCRIBE silver.mv_fact_task_vx")
            print("  Columns in silver.mv_fact_task_vx: " + ", ".join([row[0] for row in r.result_rows]))
        except:
            pass

    # =========================================
    # Step 6: Check Gold rmv_l5_task_completion
    # =========================================
    print("\n【Step 6: Gold - gold.rmv_l5_task_completion】")
    try:
        # Check all plants
        print("  All plants distribution:")
        r = client.query("""
            SELECT plant, count() as cnt
            FROM gold.rmv_l5_task_completion
            GROUP BY plant
            ORDER BY cnt DESC
        """)
        for row in r.result_rows:
            print(f"    {row[0]}: {row[1]}")
            
        # Check DG3 specific
        print(f"\n  Checking specific filter: {PLANT}/{FACTORY}/{LINE}")
        r2 = client.query(f"""
            SELECT plant, factory, line, vx_type, count() as cnt
            FROM gold.rmv_l5_task_completion
            WHERE plant = '{PLANT}'
            GROUP BY plant, factory, line, vx_type
            ORDER BY cnt DESC
            LIMIT 20
        """)
        if not r2.result_rows:
            print(f"  ❌ No data for plant='{PLANT}' in Gold RMV")
        else:
            df = pd.DataFrame(r2.result_rows, columns=r2.column_names)
            print(f"  {df.to_string(index=False)}")
            
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    diagnose()
