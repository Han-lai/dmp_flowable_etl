import pyodbc
import pandas as pd
import warnings
import sys

warnings.filterwarnings("ignore")

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'

conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'

def check_linename_asterisk():
    conn = pyodbc.connect(conn_str)
    try:
        # Check for ANY usage of '*' in lineName variable
        query = """
        SELECT DISTINCT TEXT_ as LineName
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108
        WHERE NAME_ = 'lineName'
          AND (TEXT_ LIKE '%*%' OR TEXT_ = '*')
        """
        
        print("Checking ACT_HI_VARINST for lineName containing '*'...")
        df = pd.read_sql(query, conn)
        
        if df.empty:
            print("No 'lineName' variables found containing '*'.")
        else:
            print(f"Found {len(df)} distinct values containing '*':")
            print(df.to_string(index=False))
            
        # Also let's just see some sample values to be sure what it looks like
        query_sample = """
        SELECT TOP 10 TEXT_ as LineName
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108
        WHERE NAME_ = 'lineName' AND TEXT_ IS NOT NULL
        """
        print("\nSample lineName values:")
        df_sample = pd.read_sql(query_sample, conn)
        print(df_sample.to_string(index=False))

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_linename_asterisk()
