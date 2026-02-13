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

def debug_0202_census():
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    
    tables_pair = [
        ('EmpOrgInfoMapping', f"WHERE Plant = '{plant}' AND MFGFactoryId = '{factory}'"),
        ('ProcessRoleUserMapping', f"WHERE Plant = '{plant}' AND Factory = '{factory}' AND LineName = '{line}'"),
        ('EmpNodeRoleMapping', "WHERE NodeCode LIKE '%V1_%' OR NodeCode LIKE '%V2_%' OR NodeCode LIKE '%V3_%'")
    ]
    
    try:
        print(f"Connecting to MSSQL {server}...")
        conn = pyodbc.connect(conn_str)
        
        for base_name, where_clause in tables_pair:
            # Check Base
            query_base = f"SELECT COUNT(DISTINCT EmpCode) as Cnt FROM APP_SRV_COMMON.dbo.{base_name} {where_clause}"
            # Check _0202
            query_0202 = f"SELECT COUNT(DISTINCT EmpCode) as Cnt FROM APP_SRV_COMMON.dbo.{base_name}_0202 {where_clause}"
            
            try:
                df_base = pd.read_sql(query_base, conn)
                cnt_base = df_base.iloc[0]['Cnt']
            except: cnt_base = 'Error'
            
            try:
                df_0202 = pd.read_sql(query_0202, conn)
                cnt_0202 = df_0202.iloc[0]['Cnt']
            except: cnt_0202 = 'Error'
            
            print(f"Table: {base_name}")
            print(f"  Base Count: {cnt_base}")
            print(f"  _0202 Count: {cnt_0202}")
            print("-" * 30)

        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_0202_census()
