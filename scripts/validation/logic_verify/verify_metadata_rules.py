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

def verify_metadata():
    conn = pyodbc.connect(conn_str)
    try:
        print("=== 1. Checking ProcessRoleUserMapping for wildcard LineName='*' ===")
        df_wildcard = pd.read_sql("SELECT TOP 5 * FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202 WHERE LineName = '*'", conn)
        if df_wildcard.empty:
            print("No wildcard lines found!")
        else:
            print(f"Found wildcard lines. Sample:\n{df_wildcard.to_string(index=False)}")

        print("\n=== 2. Checking Blacklist Groups ===")
        blacklist = ['ManagerUser', 'LocalAdmin', 'GlobalAdmin', 'SystemAdmin', 'InternalAudit', 'SeniorOfficers&DTO']
        blacklist_str = "', '".join(blacklist)
        
        query_bl = f"""
        SELECT g.UserGroupName, COUNT(m.EmpCode) as UserCount
        FROM APP_SRV_COMMON.dbo.EmpUserGroupMapping_0202 m 
        JOIN APP_SRV_COMMON.dbo.UserGroup_0202 g ON m.UserGroupId = g.UserGroupId 
        WHERE g.UserGroupName IN ('{blacklist_str}')
        GROUP BY g.UserGroupName
        """
        df_bl = pd.read_sql(query_bl, conn)
        print(df_bl.to_string(index=False))

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_metadata()
