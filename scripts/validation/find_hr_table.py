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

def inspect_hr_full():
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    
    try:
        print(f"Connecting to MSSQL {server}...")
        conn = pyodbc.connect(conn_str)
        
        tables = ['HR_Employee', 'HR_Employee_0202']
        
        for table in tables:
            print(f"\n--- Checking {table} ---")
            try:
                # Get columns via Schema
                query_schema = f"SELECT COLUMN_NAME FROM APP_SRV_COMMON.INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table}'"
                df = pd.read_sql(query_schema, conn)
                cols = df['COLUMN_NAME'].tolist()
                print(f"Total Columns: {len(cols)}")
                # Print all columns sorted
                for c in sorted(cols):
                    print(c)
                
                # Check for keywords
                potential = [c for c in cols if 'Status' in c or 'Active' in c or 'Resign' in c or 'State' in c]
                print(f"\nPotential Status Columns: {potential}")

            except Exception as e:
                print(f"Error checking {table}: {e}")

        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_hr_full()
