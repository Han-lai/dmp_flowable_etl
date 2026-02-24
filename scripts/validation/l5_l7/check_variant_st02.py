import clickhouse_connect
import pandas as pd

client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

PLANT = 'DG3'
FACTORY = 'SMT'
LINE = 'ST02'

def check_variant():
    print(f"Checking Variant Data for {PLANT}/{FACTORY}/{LINE}...")

    # =========================================
    # 1. Bronze: ACT_HI_VARINST
    # =========================================
    print("\n【1. Bronze: ACT_HI_VARINST】")
    try:
        # Check if line or lineName is used
        query_check_name = f"""
        SELECT NAME_, count() 
        FROM bronze.ACT_HI_VARINST_0108 
        WHERE TEXT_ = '{LINE}'
        GROUP BY NAME_
        """
        r = client.query(query_check_name)
        if not r.result_rows:
            print(f"  ❌ No Bronze variables with value '{LINE}' found.")
        else:
            print(f"  ✅ Found Bronze variables with value '{LINE}':")
            for row in r.result_rows:
                print(f"    Variable: {row[0]}, Count: {row[1]}")
                
            # Verify linkage to DG3/SMT (Sampling)
            print("    Verifying linkage to DG3/SMT...")
            # This is expensive, so just count one intersection
            q_link = f"""
            SELECT count()
            FROM bronze.ACT_HI_VARINST_0108 v_line
            WHERE v_line.TEXT_ = '{LINE}'
              AND v_line.PROC_INST_ID_ IN (
                  SELECT PROC_INST_ID_ FROM bronze.ACT_HI_VARINST_0108 
                  WHERE NAME_ = 'plant' AND TEXT_ = '{PLANT}'
              )
            """
            r_link = client.query(q_link)
            print(f"    Rows linked to {PLANT}: {r_link.result_rows[0][0]}")

    except Exception as e:
        print(f"  Error: {e}")

    # =========================================
    # 2. Silver: mv_varinst_pivoted
    # =========================================
    print("\n【2. Silver: mv_varinst_pivoted】")
    try:
        # Columns check
        r_desc = client.query("DESCRIBE silver.mv_varinst_pivoted")
        cols = [row[0] for row in r_desc.result_rows]
        # Guess line column
        l_col = next((c for c in cols if 'line' in c), 'varinst_line')
        p_col = next((c for c in cols if 'plant' in c), 'varinst_plant')
        f_col = next((c for c in cols if 'factory' in c), 'varinst_factory')
        
        print(f"  Querying silver.mv_varinst_pivoted using {l_col}...")
        
        q_silver = f"""
        SELECT count() 
        FROM silver.mv_varinst_pivoted
        WHERE {p_col} = '{PLANT}'
          AND {f_col} = '{FACTORY}'
          AND {l_col} = '{LINE}'
        """
        r_silver = client.query(q_silver)
        print(f"  Rows in mv_varinst_pivoted: {r_silver.result_rows[0][0]}")
        
    except Exception as e:
        # If MV is not queryable directly, try inner table
        print(f"  Direct query failed ({e}). Checking inner table...")
        try:
            # Find inner table
            r_inner = client.query("SELECT name FROM system.tables WHERE database='silver' AND name LIKE '.inner_id.%' AND total_rows > 100000 ORDER BY total_rows DESC LIMIT 1")
            # Usually biggest is fact or pivoted. Pivoted has 534k rows? Fact has 1.4M.
            # Let's try to match by row count from previous inspect
            # pivoted inner was .inner_id.3d23bacf... (534k)
            # fact inner was .inner_id.86c879ce... (1.4M)
            
            # Use explicit UUID from previous knowledge
            inner_tbl = ".inner_id.3d23bacf-600f-4950-8ea2-9ec6a9a2ce9d" # Assuming this is pivoted
            print(f"  Querying inner table {inner_tbl}...")
            
            q_inner = f"""
            SELECT count() FROM silver.`{inner_tbl}`
            WHERE varinst_plant = '{PLANT}'
              AND varinst_factory = '{FACTORY}'
              # AND varinst_line = '{LINE}' -- need to check column name
            """
            # Check columns of inner
            r_desc = client.query(f"DESCRIBE silver.`{inner_tbl}`")
            cols = [row[0] for row in r_desc.result_rows]
            l_col_inner = next((c for c in cols if 'line' in c), None)
            
            if l_col_inner:
                 q_inner = f"""
                    SELECT count() FROM silver.`{inner_tbl}`
                    WHERE varinst_plant = '{PLANT}'
                      AND varinst_factory = '{FACTORY}'
                      AND {l_col_inner} = '{LINE}'
                 """
                 r_inner_res = client.query(q_inner)
                 print(f"  Rows in inner table: {r_inner_res.result_rows[0][0]}")
            else:
                 print(f"  Could not find line column in inner table. Cols: {cols}")

        except Exception as e2:
            print(f"  Error querying inner: {e2}")

if __name__ == "__main__":
    check_variant()
