import clickhouse_connect
import pandas as pd

client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

PLANT = 'DG3'
FACTORY = 'SMT'
LINE = 'ST02'

def check_dim():
    print(f"Checking Dimensions for {PLANT}/{FACTORY}/{LINE}...")
    
    # Check mv_dim_mfg_five_level
    try:
        # Check columns first
        r = client.query("DESCRIBE silver.mv_dim_mfg_five_level")
        cols = [row[0] for row in r.result_rows]
        print(f"  mv_dim_mfg_five_level columns: {cols}")
        
        # Columns guessing
        p = next((c for c in ['plant_code', 'plant'] if c in cols), None)
        f = next((c for c in ['factory_code', 'factory'] if c in cols), None)
        l = next((c for c in ['line_code', 'line_name', 'line'] if c in cols), None)
        
        if not (p and f and l):
            print(f"  ❌ Could not map columns. Found: {cols}")
            return

        print(f"  Querying silver.mv_dim_mfg_five_level with {p}, {f}, {l}...")
        
        # Query specifically for ST04
        query = f"""
            SELECT count() FROM silver.mv_dim_mfg_five_level
            WHERE {p} = '{PLANT}' 
              AND {f} = '{FACTORY}'
              AND {l} = 'ST04'
        """
        try:
            r = client.query(query)
            cnt = r.result_rows[0][0]
            
            if cnt == 0:
                print(f"\n  ❌ {PLANT}/{FACTORY}/ST04 is MISSING from dimension table!")
            else:
                print(f"\n  ✅ {PLANT}/{FACTORY}/ST04 is PRESENT in dimension table.")
                    
        except Exception as e:
            print(f"  Query error: {e}")
                    
        except Exception as e:
            print(f"  Query error: {e}")
            
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    check_dim()
