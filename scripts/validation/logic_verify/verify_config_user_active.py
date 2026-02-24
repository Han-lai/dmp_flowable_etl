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

def verify_exclusion_logic():
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'

    query = f"""
    WITH 
    UserVx AS (
        SELECT DISTINCT EmpCode 
        FROM APP_SRV_COMMON.dbo.EmpNodeRoleMapping
        WHERE NodeCode LIKE '%V1_%' OR NodeCode LIKE '%V2_%' OR NodeCode LIKE '%V3_%'
    ),
    UserLocation AS (
        SELECT EmpCode FROM APP_SRV_COMMON.dbo.EmpOrgInfoMapping
        WHERE Plant = '{plant}' AND MFGFactoryId = '{factory}'
        UNION
        SELECT EmpCode FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping
        WHERE Plant = '{plant}' AND Factory = '{factory}' AND LineName = '{line}'
    ),
    Candidates AS (
        SELECT DISTINCT l.EmpCode
        FROM UserLocation l
        JOIN UserVx uv ON l.EmpCode = uv.EmpCode
    ),
    UserGroups AS (
        SELECT m.EmpCode, g.UserGroupName
        FROM APP_SRV_COMMON.dbo.EmpUserGroupMapping m
        JOIN APP_SRV_COMMON.dbo.UserGroup g ON m.UserGroupId = g.UserGroupId
        WHERE m.EmpCode IN (SELECT EmpCode FROM Candidates)
    ),
    ExcludeFlags AS (
        SELECT 
            EmpCode,
            MAX(CASE WHEN UserGroupName = 'ManagerUser' THEN 1 ELSE 0 END) as IsManager,
            MAX(CASE WHEN UserGroupName = 'InternalAudit' THEN 1 ELSE 0 END) as IsAudit,
            MAX(CASE WHEN UserGroupName = 'SeniorOfficers&DTO' THEN 1 ELSE 0 END) as IsSenior,
            MAX(CASE WHEN UserGroupName IN ('ManagerUser', 'InternalAudit', 'SeniorOfficers&DTO') THEN 1 ELSE 0 END) as IsExcludedParams
        FROM UserGroups
        GROUP BY EmpCode
    )
    
    SELECT 
        'Total Candidates (Location+Vx)' as Scenario,
        COUNT(DISTINCT c.EmpCode) as Count
    FROM Candidates c
    
    UNION ALL
    
    SELECT 
        'Exclude Manager Only',
        COUNT(DISTINCT c.EmpCode)
    FROM Candidates c
    LEFT JOIN ExcludeFlags e ON c.EmpCode = e.EmpCode
    WHERE ISNULL(e.IsManager, 0) = 0
    
    UNION ALL

    SELECT 
        'Exclude Manager/Audit/Senior',
        COUNT(DISTINCT c.EmpCode)
    FROM Candidates c
    LEFT JOIN ExcludeFlags e ON c.EmpCode = e.EmpCode
    WHERE ISNULL(e.IsExcludedParams, 0) = 0
    """
    
    try:
        print(f"Connecting to MSSQL {server}...")
        conn = pyodbc.connect(conn_str)
        
        print("Checking Exclusion Logic...")
        try:
            df = pd.read_sql(query, conn)
            print(df.to_string(index=False))
            
        except Exception as e:
            print(f"Failed to query: {e}")

        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_exclusion_logic()
