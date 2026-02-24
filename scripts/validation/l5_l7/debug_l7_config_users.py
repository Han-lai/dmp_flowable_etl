import pyodbc
import pandas as pd
import warnings
import sys

# Suppress warnings
warnings.filterwarnings("ignore")

# Connection Details
server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'

def debug_l7_config_users():
    # Target date doesn't matter for Config User as it is static mapping? 
    # Or maybe it changes over time? Assuming static for now.
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    
    # Debug Query: List users found by logic
    query = f"""
    WITH 
    UserGroups AS (
        SELECT m.EmpCode, g.UserGroupName
        FROM APP_SRV_COMMON.dbo.EmpUserGroupMapping m
        JOIN APP_SRV_COMMON.dbo.UserGroup g ON m.UserGroupId = g.UserGroupId
    ),
    UserFlags AS (
        SELECT 
            EmpCode,
            STRING_AGG(UserGroupName, ', ') as AllGroups,
            MAX(CASE WHEN UserGroupName IN ('ManagerUser', 'LocalAdmin', 'GlobalAdmin', 'SystemAdmin', 'InternalAudit', 'SeniorOfficers&DTO') THEN 1 ELSE 0 END) as HasExclude,
            MAX(CASE WHEN UserGroupName IN ('User', 'PMUser', 'PowerUser') THEN 1 ELSE 0 END) as HasWhitelistV1,
            CASE WHEN COUNT(*) = 1 AND MAX(UserGroupName) = 'User' THEN 1 ELSE 0 END as IsStrictUser
        FROM UserGroups
        GROUP BY EmpCode
    ),
    UserVx AS (
        SELECT DISTINCT 
            EmpCode, 
            CASE 
                WHEN NodeCode LIKE '%V1_%' THEN 'V1'
                WHEN NodeCode LIKE '%V2_%' THEN 'V2'
                WHEN NodeCode LIKE '%V3_%' THEN 'V3'
                ELSE 'Other'
            END as VxType
        FROM APP_SRV_COMMON.dbo.EmpNodeRoleMapping
        WHERE NodeCode LIKE '%V1_%' OR NodeCode LIKE '%V2_%' OR NodeCode LIKE '%V3_%'
    ),
    UserLocation_Org AS (
        SELECT EmpCode, 'Org_Factory' as Source
        FROM APP_SRV_COMMON.dbo.EmpOrgInfoMapping
        WHERE Plant = '{plant}' AND MFGFactoryId = '{factory}'
    ),
    UserLocation_Line AS (
        SELECT EmpCode, 'Org_Line' as Source
        FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping
        WHERE Plant = '{plant}' AND Factory = '{factory}' AND LineName = '{line}'
    ),
    UserLocation AS (
        SELECT EmpCode, Source FROM UserLocation_Org
        UNION
        SELECT EmpCode, Source FROM UserLocation_Line
    )
    
    -- 1. Summary Counts
    SELECT 
        '1. Location Only' as Metric,
        COUNT(DISTINCT l.EmpCode) as Count
    FROM UserLocation l
    
    UNION ALL
    
    SELECT 
        '2. Location + Vx Role',
        COUNT(DISTINCT l.EmpCode)
    FROM UserLocation l
    JOIN UserVx uv ON l.EmpCode = uv.EmpCode
    
    UNION ALL
    
    SELECT 
        '3. Location + Vx + Whitelist (User/PM/Power)',
        COUNT(DISTINCT l.EmpCode)
    FROM UserLocation l
    JOIN UserVx uv ON l.EmpCode = uv.EmpCode
    JOIN UserFlags u ON l.EmpCode = u.EmpCode
    WHERE u.HasWhitelistV1 = 1
    
    UNION ALL

    SELECT 
        '4. Current Logic (Strict + Exclude)',
        COUNT(DISTINCT l.EmpCode)
    FROM UserLocation l
    JOIN UserVx uv ON l.EmpCode = uv.EmpCode
    JOIN UserFlags u ON l.EmpCode = u.EmpCode
    WHERE 
        u.HasExclude = 0
        AND (
            (uv.VxType = 'V1' AND u.HasWhitelistV1 = 1)
            OR
            (uv.VxType IN ('V2', 'V3') AND u.IsStrictUser = 1)
        )
    UNION ALL
    
    SELECT 
        '5. Location + Exclude Admin (No Vx Check)',
        COUNT(DISTINCT l.EmpCode)
    FROM UserLocation l
    JOIN UserFlags u ON l.EmpCode = u.EmpCode
    WHERE u.HasExclude = 0

    UNION ALL
    
    SELECT 
        '6. Location + Vx + Exclude Admin (No Whitelist/Strict)',
        COUNT(DISTINCT l.EmpCode)
    FROM UserLocation l
    JOIN UserVx uv ON l.EmpCode = uv.EmpCode
    JOIN UserFlags u ON l.EmpCode = u.EmpCode
    WHERE u.HasExclude = 0
    UNION ALL

    UNION ALL

    -- 7. Analyze Location Source
    SELECT 
        'Location Source: ' + Source,
        COUNT(DISTINCT EmpCode)
    FROM UserLocation
    GROUP BY Source

    UNION ALL

    -- 8. Check HREmployee Status (If exists)
    -- Assuming Table is dbo.HREmployee and has Status/UserStatus col
    -- Use try-catch or safe check? In SQL simply join. 
    -- If table doesn't exist, this whole query might fail.
    -- I'll first list tables in debug_mssql_schema.py to be safe? 
    -- Alternatively, assume commonly used names.
    SELECT 
        'Active Employee Only (Join HREmployee)',
        COUNT(DISTINCT l.EmpCode)
    FROM UserLocation l
    JOIN UserVx uv ON l.EmpCode = uv.EmpCode
    JOIN APP_SRV_COMMON.dbo.HREmployee hr ON l.EmpCode = hr.EmpID -- Guessing EmpID or EmpCode
    WHERE hr.Status = 'Active' -- Guessing Status value
    """
    """
    
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    
    try:
        print(f"Connecting to MSSQL {server}...")
        conn = pyodbc.connect(conn_str)
        
        print(f"Executing Scenario Counts...")
        df = pd.read_sql(query, conn)
        
        print("\n--- Scenario Results ---")
        print(df.to_string(index=False))
        
        conn.close()
        
    except Exception as e:
        print(f"Error ({type(e).__name__}): {e}")

if __name__ == "__main__":
    debug_l7_config_users()
