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

# Expected values (V3/CNE/WJ2/NBU/E5) from user
EXPECTED = {
    '2025-12-25': {'total': 192, 'todo':  26, 'doing':   1, 'done': 165, 'acc':  40},
    '2025-12-26': {'total': 148, 'todo':  56, 'doing':  12, 'done':  80, 'acc':  76},
    '2025-12-27': {'total': 110, 'todo':  14, 'doing':   4, 'done':  92, 'acc':  44},
    '2025-12-28': {'total':  11, 'todo':   3, 'doing':   0, 'done':   8, 'acc':  46},
    '2025-12-29': {'total':  88, 'todo':   3, 'doing':  22, 'done':  63, 'acc':  40},
    '2025-12-30': {'total': 262, 'todo':   8, 'doing':  60, 'done': 194, 'acc':  95},
    '2025-12-31': {'total': 210, 'todo':   9, 'doing':   5, 'done': 196, 'acc':  97},
}

def verify_wj2_clickhouse_logic():
    dates = pd.date_range(start='2025-12-25', end='2025-12-31')
    
    # Original ClickHouse Silver Logic for V3
    # Priority 1: TASK_DEF_KEY_ LIKE 'V3%' -> 'V3'
    # And we want ONLY V3 tasks.
    vx_v3_ch_rule = """
    t.TASK_DEF_KEY_ LIKE 'V3%'
    """
    
    # Exclusion rules from Silver
    excl = """
    AND NOT EXISTS (
        SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_bp
        WHERE v_bp.TASK_ID_ = t.ID_
          AND v_bp.NAME_ = 'autoComplete' AND v_bp.LONG_ = 1
    )
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
    
    print("L5 Task Completion - V3 (Original ClickHouse Logic) / WJ2/NBU/E5")
    print(f"V3 Rule: {vx_v3_ch_rule.strip()}")
    print(f"{'Date':<12} | {'Total':>5} {'Exp':>5} | {'Todo':>5} {'Exp':>4} | {'Doing':>5} {'Exp':>4} | {'Done':>5} {'Exp':>4} | {'Acc':>5} {'Exp':>4} | Match")
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
                  AND v2.NAME_='factory' AND v2.TEXT_='NBU'
                  AND v3.NAME_='lineName' AND v3.TEXT_='E5'
            ),
            FT AS (
                SELECT DISTINCT t.ID_, t.START_TIME_, t.CLAIM_TIME_, t.END_TIME_
                FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
                JOIN TargetInsts ti ON t.PROC_INST_ID_ = ti.PROC_INST_ID_
                WHERE (CAST(t.START_TIME_ AS DATE)='{ds}' OR CAST(t.CLAIM_TIME_ AS DATE)='{ds}' OR CAST(t.END_TIME_ AS DATE)='{ds}')
                AND {vx_v3_ch_rule}
                {excl}
            )
            SELECT
                COUNT(*) AS total_task,
                SUM(CASE WHEN '{ds}' < CAST(CLAIM_TIME_ AS DATE) OR (CLAIM_TIME_ IS NULL AND (END_TIME_ IS NULL OR '{ds}' < CAST(END_TIME_ AS DATE))) THEN 1 ELSE 0 END) AS todo,
                SUM(CASE WHEN CLAIM_TIME_ IS NOT NULL AND '{ds}' >= CAST(CLAIM_TIME_ AS DATE) AND (END_TIME_ IS NULL OR '{ds}' < CAST(END_TIME_ AS DATE)) THEN 1 ELSE 0 END) AS doing,
                SUM(CASE WHEN END_TIME_ IS NOT NULL AND '{ds}' >= CAST(END_TIME_ AS DATE) THEN 1 ELSE 0 END) AS done
            FROM FT
            """
            
            qa = f"""
            WITH TargetInsts AS (
                SELECT v1.PROC_INST_ID_
                FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v1
                JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v2 ON v1.PROC_INST_ID_ = v2.PROC_INST_ID_
                JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v3 ON v1.PROC_INST_ID_ = v3.PROC_INST_ID_
                WHERE v1.NAME_='plant' AND v1.TEXT_='WJ2'
                  AND v2.NAME_='factory' AND v2.TEXT_='NBU'
                  AND v3.NAME_='lineName' AND v3.TEXT_='E5'
            )
            SELECT COUNT(DISTINCT t.ID_) AS acc
            FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
            JOIN TargetInsts ti ON t.PROC_INST_ID_ = ti.PROC_INST_ID_
            WHERE CAST(t.START_TIME_ AS DATE) <= '{ds}'
              AND (t.END_TIME_ IS NULL OR CAST(t.END_TIME_ AS DATE) > '{ds}')
              AND (CAST(t.START_TIME_ AS DATE) >= DATEADD(day,-6,'{ds}') OR (t.CLAIM_TIME_ IS NOT NULL AND CAST(t.CLAIM_TIME_ AS DATE) >= DATEADD(day,-6,'{ds}')))
              AND {vx_v3_ch_rule}
              {excl}
            """
            
            df = pd.read_sql(q, conn)
            total = int(df['total_task'].iloc[0] or 0)
            todo = int(df['todo'].iloc[0] or 0)
            doing = int(df['doing'].iloc[0] or 0)
            done = int(df['done'].iloc[0] or 0)
            
            acc = int(pd.read_sql(qa, conn)['acc'].iloc[0] or 0)
            
            def c(a, k): return "✓" if a == exp[k] else f"Δ{a-exp[k]:+d}"
            ok = "✅" if all([total==exp['total'], todo==exp['todo'], doing==exp['doing'], done==exp['done'], acc==exp['acc']]) else "❌"
            print(f"{ds:<12} | {total:>5} {c(total,'total'):>5} | {todo:>5} {c(todo,'todo'):>4} | {doing:>5} {c(doing,'doing'):>4} | {done:>5} {c(done,'done'):>4} | {acc:>5} {c(acc,'acc'):>4} | {ok}")
            sys.stdout.flush()
        except Exception as e:
            print(f"{ds:<12} | ERROR: {e}")
            sys.stdout.flush()
        finally:
            conn.close()
            
    print("-" * 100)

if __name__ == "__main__":
    verify_wj2_clickhouse_logic()
