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

# Expected values (V1/CNS/DG3/SMT/ST02)
EXPECTED = {
    '2025-12-25': {'total': 706, 'todo': 164, 'doing': 124, 'done': 418, 'acc': 458},
    '2025-12-26': {'total': 649, 'todo': 104, 'doing': 248, 'done': 297, 'acc': 646},
    '2025-12-27': {'total': 789, 'todo':  90, 'doing': 190, 'done': 509, 'acc': 460},
    '2025-12-28': {'total':  45, 'todo':   7, 'doing':  11, 'done':  27, 'acc': 445},
    '2025-12-29': {'total': 345, 'todo':  82, 'doing':  90, 'done': 173, 'acc': 403},
    '2025-12-30': {'total': 286, 'todo':  36, 'doing':  84, 'done': 166, 'acc': 362},
    '2025-12-31': {'total': 136, 'todo':  21, 'doing':  44, 'done':  71, 'acc': 354},
}

# V1 moNumber prefixes (moNumber-priority rule)
V1_MO_PREFIXES = "('315','196','199','200','210','212','213')"

def verify():
    dates = pd.date_range(start='2025-12-25', end='2025-12-31')
    
    # Vx V1 = moNumber priority: mo prefix in V1 list → V1 (regardless of TASK_DEF_KEY)
    vx_v1 = f"""
    EXISTS (
        SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_mo
        WHERE v_mo.PROC_INST_ID_ = t.PROC_INST_ID_
          AND v_mo.NAME_ = 'moNumber'
          AND LEFT(v_mo.TEXT_, 3) IN {V1_MO_PREFIXES}
    )
    """
    
    loc = """
    AND EXISTS (SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v WHERE v.PROC_INST_ID_=t.PROC_INST_ID_ AND v.NAME_='plant' AND v.TEXT_='DG3')
    AND EXISTS (SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v WHERE v.PROC_INST_ID_=t.PROC_INST_ID_ AND v.NAME_='factory' AND v.TEXT_='SMT')
    AND EXISTS (SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v WHERE v.PROC_INST_ID_=t.PROC_INST_ID_ AND v.NAME_='lineName' AND v.TEXT_='ST02')
    """
    
    excl = """
    AND t.NAME_ NOT LIKE '%Notify%'
    AND t.NAME_ NOT LIKE '%Dummy%'
    AND t.DELETE_REASON_ IS NULL
    """
    
    print("L5 Task Completion - V1 (moNumber priority) / DG3/SMT/ST02")
    print(f"V1 Rule: moNumber prefix IN {V1_MO_PREFIXES}")
    print(f"{'Date':<12} | {'Total':>5} {'Exp':>5} | {'Todo':>5} {'Exp':>4} | {'Doing':>5} {'Exp':>4} | {'Done':>5} {'Exp':>4} | {'Acc':>5} {'Exp':>4} | Match")
    print("-" * 100)
    
    for d in dates:
        ds = d.strftime('%Y-%m-%d')
        exp = EXPECTED[ds]
        conn = pyodbc.connect(conn_str)
        try:
            q = f"""
            WITH TargetInsts AS (
                -- First, identify process instances matching the location
                SELECT v1.PROC_INST_ID_
                FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v1
                JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v2 ON v1.PROC_INST_ID_ = v2.PROC_INST_ID_
                JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v3 ON v1.PROC_INST_ID_ = v3.PROC_INST_ID_
                WHERE v1.NAME_='plant' AND v1.TEXT_='DG3'
                  AND v2.NAME_='factory' AND v2.TEXT_='SMT'
                  AND v3.NAME_='lineName' AND v3.TEXT_='ST02'
            ),
            FT AS (
                -- Then, get Tasks for those instances and apply V1 rule
                SELECT DISTINCT t.ID_, t.START_TIME_, t.CLAIM_TIME_, t.END_TIME_
                FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
                JOIN TargetInsts ti ON t.PROC_INST_ID_ = ti.PROC_INST_ID_
                WHERE (CAST(t.START_TIME_ AS DATE)='{ds}' OR CAST(t.CLAIM_TIME_ AS DATE)='{ds}' OR CAST(t.END_TIME_ AS DATE)='{ds}')
                  AND EXISTS (
                      SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_mo
                      WHERE v_mo.PROC_INST_ID_ = t.PROC_INST_ID_
                        AND v_mo.NAME_ = 'moNumber'
                        AND LEFT(v_mo.TEXT_, 3) IN {V1_MO_PREFIXES}
                  )
                  AND t.NAME_ NOT LIKE '%Notify%'
                  AND t.NAME_ NOT LIKE '%Dummy%'
                  AND t.DELETE_REASON_ IS NULL
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
            
            qa = f"""
            WITH TargetInsts AS (
                SELECT v1.PROC_INST_ID_
                FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v1
                JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v2 ON v1.PROC_INST_ID_ = v2.PROC_INST_ID_
                JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v3 ON v1.PROC_INST_ID_ = v3.PROC_INST_ID_
                WHERE v1.NAME_='plant' AND v1.TEXT_='DG3'
                  AND v2.NAME_='factory' AND v2.TEXT_='SMT'
                  AND v3.NAME_='lineName' AND v3.TEXT_='ST02'
            )
            SELECT COUNT(DISTINCT t.ID_) AS acc
            FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
            JOIN TargetInsts ti ON t.PROC_INST_ID_ = ti.PROC_INST_ID_
            WHERE CAST(t.START_TIME_ AS DATE) <= '{ds}'
              AND (t.END_TIME_ IS NULL OR CAST(t.END_TIME_ AS DATE) > '{ds}')
              AND (CAST(t.START_TIME_ AS DATE) >= DATEADD(day,-6,'{ds}') OR (t.CLAIM_TIME_ IS NOT NULL AND CAST(t.CLAIM_TIME_ AS DATE) >= DATEADD(day,-6,'{ds}')))
              AND EXISTS (
                  SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_mo
                  WHERE v_mo.PROC_INST_ID_ = t.PROC_INST_ID_
                    AND v_mo.NAME_ = 'moNumber'
                    AND LEFT(v_mo.TEXT_, 3) IN {V1_MO_PREFIXES}
              )
              AND t.NAME_ NOT LIKE '%Notify%'
              AND t.NAME_ NOT LIKE '%Dummy%'
              AND t.DELETE_REASON_ IS NULL
            """
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
    verify()
