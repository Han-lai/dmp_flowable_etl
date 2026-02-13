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

def inspect_stats_table():
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    
    try:
        print(f"Connecting to MSSQL {server}...")
        conn = pyodbc.connect(conn_str)
        
        table = 'FlowableTaskStats_0202'
        print(f"\n--- Checking {table} ---")
        
        # Get columns
        try:
            query = f"SELECT TOP 1 * FROM APP_SRV_COMMON.dbo.{table}"
            df = pd.read_sql(query, conn)
            print("Columns:")
            print(df.columns.tolist())
            print("\nSample Data:")
            print(df.to_string())
        except Exception as e:
            print(f"Error accessing table: {e}")
            
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_stats_table()
