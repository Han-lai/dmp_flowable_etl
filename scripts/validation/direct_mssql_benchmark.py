
import pyodbc

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_COMMON' # Default

def get_mssql_conn():
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};UID={username};PWD={password}'
    try:
        return pyodbc.connect(conn_str, timeout=10)
    except Exception as e:
        print(f"Failed to connect: {e}")
        return None

conn = get_mssql_conn()
if conn:
    print("✅ Connected to MSSQL")
    cursor = conn.cursor()
    
    # Try the user's query exactly
    query = """
    SELECT count(*) FROM flowable_analytics.dbo.FlowableTaskStats i
    WHERE (
        CAST(i.TaskCreateDate AS DATE) = '2025-12-25'
        OR CAST(i.TaskEndDate AS DATE) = '2025-12-25'
        OR CAST(i.TaskClaimDate AS DATE) = '2025-12-25'
    )
    and i.TaskBypass ='N' and i.TaskStatus  in ('DONE')
    and (
        i.MoNumber NOT LIKE 'E%' 
        AND i.MoNumber NOT LIKE 'C%' 
        AND i.MoNumber NOT LIKE 'Q%' 
        AND i.MoNumber NOT LIKE 'R%'
    )
    """
    
    # Try different database names if flowable_analytics is the database
    # or just try the query as provided
    try:
        print("Executing user's exact query (guessing flowable_analytics is a database)...")
        cursor.execute(query)
        res = cursor.fetchone()
        print(f"Count: {res[0]}")
    except Exception as e:
        print(f"Exact query failed: {e}")
        print("Searching for the table in other locations...")
        
        # Search for table named FlowableTaskStats
        cursor.execute("SELECT name FROM sys.databases")
        dbs = [row.name for row in cursor.fetchall()]
        print(f"Available Databases: {dbs}")
        
    conn.close()
else:
    print("❌ Could not establish connection.")
