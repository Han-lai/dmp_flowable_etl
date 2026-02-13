import pyodbc
import pandas as pd
import warnings

# Suppress warnings
warnings.filterwarnings("ignore")

# Connection Details
server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'

def debug_hr():
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    
    try:
        print(f"Connecting to MSSQL {server}...")
        conn = pyodbc.connect(conn_str)
        
        # 1. Check Table Name and Columns
        print("Checking HREmployee (dbo)...")
        try:
            query = "SELECT TOP 3 * FROM APP_SRV_COMMON.dbo.HREmployee"
            df = pd.read_sql(query, conn)
            print(df.to_string())
            print("\nColumns:", df.columns.tolist())
        except Exception as e:
            print(f"Failed HREmployee: {e}")
            # Try removing dbo?
            try:
                query = "SELECT TOP 3 * FROM APP_SRV_COMMON.HREmployee" # unlikely syntax
                # Or check schema
            except:
                pass

        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_hr()
