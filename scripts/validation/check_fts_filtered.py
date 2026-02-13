import pyodbc
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'

conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
conn = pyodbc.connect(conn_str)

def check_fts_filtered_nov():
    plant = 'WJ2'
    factory = 'NBU'
    line = 'E5'
    dates = pd.date_range(start='2025-11-24', end='2025-11-30').strftime('%Y-%m-%d').tolist()
    expected = [14, 10, 9, 8, 9, 9, 1]
    
    config_cte = f"""
    ConfigUsers AS (
        SELECT DISTINCT EmpCode
        FROM APP_SRV_COMMON.dbo.ProcessRoleUserMapping_0202
        WHERE Plant = '{plant}' AND Factory = '{factory}' 
          AND LineName IN ('E5', '*')
    )
    """
    
    print(f"=== FlowableTaskStats_0202 + Config Filter (Pool=57) ===")
    
    query = f"""
    WITH {config_cte}
    SELECT TaskEndDate, COUNT(DISTINCT TaskAssignee) as FilteredUsers
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats_0202
    WHERE Plant = '{plant}' AND Factory = '{factory}' AND Line = '{line}'
      AND TaskEndDate BETWEEN '2025-11-24' AND '2025-11-30'
      AND TaskAssignee IN (SELECT EmpCode FROM ConfigUsers)
    GROUP BY TaskEndDate
    ORDER BY TaskEndDate
    """
    
    df = pd.read_sql(query, conn)
    
    for i, target_date in enumerate(dates):
        res = df[df['TaskEndDate'] == target_date]
        count = res.iloc[0]['FilteredUsers'] if len(res) > 0 else 0
        exp = expected[i]
        match = "✅" if count == exp else f"❌ ({count-exp})"
        print(f"{target_date}: Count={count}, Exp={exp} -> {match}")

if __name__ == "__main__":
    check_fts_filtered_nov()
    conn.close()
