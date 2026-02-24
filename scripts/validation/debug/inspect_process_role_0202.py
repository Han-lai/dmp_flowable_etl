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

def inspect_0202_nbu():
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    
    plant = 'WJ2'
    factory = 'NBU'
    
    try:
        print(f"Connecting to MSSQL {server}...")
        conn = pyodbc.connect(conn_str)
        
        # 1. Process Role (NBU Only)
        print(f"\n--- ProcessRoleUserMapping_0202 (NBU) ---")
        query_proc = f"""
        SELECT Factory, LineName, COUNT(DISTINCT EmpCode) as UserCount
        FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202
        WHERE Plant = '{plant}' AND Factory LIKE '%NBU%'
        GROUP BY Factory, LineName
        ORDER BY Factory, LineName
        """
        try:
            df_proc = pd.read_sql(query_proc, conn)
            print(df_proc.to_string(index=False))
        except Exception as e:
            print(f"Error querying ProcessRole: {e}")
            
        # 2. EmpOrgInfoMapping_0202 Columns
        print(f"\n--- EmpOrgInfoMapping_0202 Columns ---")
        try:
            df_col = pd.read_sql("SELECT TOP 1 * FROM APP_SRV_COMMON.dbo.EmpOrgInfoMapping_0202", conn)
            print(df_col.columns.tolist())
            print(df_col.to_string())
        except Exception as e:
            print(f"Error querying EmpOrg Info: {e}")
            
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_0202_nbu()
