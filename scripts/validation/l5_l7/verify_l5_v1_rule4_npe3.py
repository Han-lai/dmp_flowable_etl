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

# Expected values (V1/CNE/WJ2/NPE/NPE3) from user
EXPECTED = {
    '2025-12-25': {'total': 203, 'todo':   8, 'doing':  73, 'done': 122, 'acc': 222},
    '2025-12-26': {'total': 158, 'todo':  36, 'doing':  67, 'done':  55, 'acc': 285},
    '2025-12-27': {'total':  69, 'todo':   5, 'doing':  30, 'done':  34, 'acc': 274},
    '2025-12-28': {'total':   2, 'todo':   2, 'doing':   0, 'done':   0, 'acc': 271},
    '2025-12-29': {'total': 123, 'todo':   0, 'doing':  41, 'done':  82, 'acc': 272},
    '2025-12-30': {'total': 237, 'todo': 118, 'doing':  44, 'done':  75, 'acc': 347},
    '2025-12-31': {'total': 243, 'todo':   2, 'doing': 129, 'done': 112, 'acc': 316},
}

# Removed 315 per user suggestion
VX_V1_MO_PREFIXES = ['196', '199', '200', '210', '212', '213']

def verify():
    dates = pd.date_range(start='2025-12-25', end='2025-12-31')
    
    mo_conditions = " OR ".join([f"v_mo.TEXT_ LIKE '{p}%'" for p in VX_V1_MO_PREFIXES])
    
    # Prioritizing moNumber over TASK_DEF_KEY (ClickHouse fix test)
    vx_v1_rule = f"""
    (
        EXISTS (
            SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_mo
            WHERE v_mo.PROC_INST_ID_ = t.PROC_INST_ID_
              AND v_mo.NAME_ = 'moNumber'
              AND ({mo_conditions})
        )
        OR 
        (
            t.TASK_DEF_KEY_ LIKE 'V1%'
            AND NOT EXISTS (
                SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_mo
                WHERE v_mo.PROC_INST_ID_ = t.PROC_INST_ID_
                  AND v_mo.NAME_ = 'moNumber'
                  AND ({mo_conditions})
            )
        )
    )
    """
    
    # Exclusion rules from Silver
    excl = """
    AND NOT EXISTS (
        SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_bp
        WHERE v_bp.TASK_ID_ = t.ID_
          AND v_bp.NAME_ = 'autoComplete' AND v_bp.LONG_ = 1
    )
    AND t.TASK_DEF_KEY_ NOT LIKE 'E%'
    AND t.TASK_DEF_KEY_ NOT LIKE 'C%'
    AND NOT EXISTS (
        SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_qr
        WHERE v_qr.PROC_INST_ID_ = t.PROC_INST_ID_
          AND v_qr.NAME_ = 'moNumber'
          AND (v_qr.TEXT_ LIKE 'Q%' OR v_qr.TEXT_ LIKE 'R%')
    )
    AND t.NAME_ NOT LIKE '%Notify%'
    AND t.NAME_ NOT LIKE '%Dummy%'
    AND t.DELETE_REASON_ IS NULL
    """
    
    print("L5 Task Completion - V1 / WJ2/NPE/NPE3 (Rule 4 applied, 315 REMOVED)")
    print(f"V1 Rule: moNumber IN ({','.join(VX_V1_MO_PREFIXES)}) OR TASK_DEF_KEY_ LIKE 'V1%'")
    print("-" * 100)
    
    for d in dates:
        ds = d.strftime('%Y-%m-%d')
        exp = EXPECTED[ds]
        conn = pyodbc.connect(conn_str)
        try:
            q = f"""
            WITH TargetInsts AS (
                SELECT v1.PROC_INST_ID_
                FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v1
                JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v2 ON v1.PROC_INST_ID_ = v2.PROC_INST_ID_
                JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v3 ON v1.PROC_INST_ID_ = v3.PROC_INST_ID_
                WHERE v1.NAME_='plant' AND v1.TEXT_='WJ2'
                  AND v2.NAME_='factory' AND v2.TEXT_='NPE'
                  AND v3.NAME_='lineName' AND v3.TEXT_='NPE3'
            ),
            FT AS (
                SELECT DISTINCT t.ID_, t.START_TIME_, t.CLAIM_TIME_, t.END_TIME_
                FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
                JOIN TargetInsts ti ON t.PROC_INST_ID_ = ti.PROC_INST_ID_
                WHERE (CAST(t.START_TIME_ AS DATE)='{ds}' OR CAST(t.CLAIM_TIME_ AS DATE)='{ds}' OR CAST(t.END_TIME_ AS DATE)='{ds}')
                AND {vx_v1_rule}
                {excl}
            )
            SELECT
                COUNT(*) AS total_task,
                SUM(CASE WHEN '{ds}' < CAST(CLAIM_TIME_ AS DATE) OR (CLAIM_TIME_ IS NULL AND (END_TIME_ IS NULL OR '{ds}' < CAST(END_TIME_ AS DATE))) THEN 1 ELSE 0 END) AS todo,
                SUM(CASE WHEN CLAIM_TIME_ IS NOT NULL AND '{ds}' >= CAST(CLAIM_TIME_ AS DATE) AND (END_TIME_ IS NULL OR '{ds}' < CAST(END_TIME_ AS DATE)) THEN 1 ELSE 0 END) AS doing,
                SUM(CASE WHEN END_TIME_ IS NOT NULL AND '{ds}' >= CAST(END_TIME_ AS DATE) THEN 1 ELSE 0 END) AS done
            FROM FT
            """
            
            df = pd.read_sql(q, conn)
            total = int(df['total_task'].iloc[0] or 0)
            todo = int(df['todo'].iloc[0] or 0)
            doing = int(df['doing'].iloc[0] or 0)
            done = int(df['done'].iloc[0] or 0)
            
            def c(a, k): return "[OK]" if a == exp[k] else f"D{a-exp[k]:+d}"
            ok = "[PASS]" if all([total==exp['total'], todo==exp['todo'], doing==exp['doing'], done==exp['done']]) else "[FAIL]"
            print(f"{ds:<12} | {total:>5} {c(total,'total'):>5} | {todo:>5} {c(todo,'todo'):>4} | {doing:>5} {c(doing,'doing'):>4} | {done:>5} {c(done,'done'):>4} | {ok}")
        except Exception as e:
            print(f"{ds:<12} | ERROR: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    verify()
