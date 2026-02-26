import pyodbc
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'
conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'

def check_bypass_vars():
    # 這是原本抓出 336 筆任務的 SQL，不做除了 autoComplete=1 (LONG_=1), Dummy/Notify 以外的排除
    # 但為了找出真相，我們連原本的排除條件都拔掉，直接抓所有 12-25 END_TIME_ 有值的 DG3 (V3)
    ds = '2025-12-25'
    
    q_tasks = f"""
    WITH TargetInsts AS (
        SELECT v1.PROC_INST_ID_, v1.TEXT_ as plant, v2.TEXT_ as factory
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v1
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v2 ON v1.PROC_INST_ID_ = v2.PROC_INST_ID_
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v3 ON v1.PROC_INST_ID_ = v3.PROC_INST_ID_
        WHERE v1.NAME_='plant' AND v1.TEXT_='DG3'
          AND v2.NAME_='factory' AND v2.TEXT_='SMT'
          AND v3.NAME_='lineName' AND v3.TEXT_='ST02'
    ),
    FT AS (
        SELECT t.ID_ as TASK_ID_, t.PROC_INST_ID_, t.NAME_, t.TASK_DEF_KEY_
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
        JOIN TargetInsts ti ON t.PROC_INST_ID_ = ti.PROC_INST_ID_
        WHERE CAST(t.END_TIME_ AS DATE) = '{ds}'
          AND t.TASK_DEF_KEY_ LIKE 'V3%'
          AND t.DELETE_REASON_ IS NULL
    )
    SELECT * FROM FT
    """
    
    conn = pyodbc.connect(conn_str)
    df_tasks = pd.read_sql(q_tasks, conn)
    
    task_ids = tuple(df_tasks['TASK_ID_'].dropna().unique().tolist())
    proc_ids = tuple(df_tasks['PROC_INST_ID_'].dropna().unique().tolist())
    
    print(f"撈出 {ds} DG3/SMT/ST02 (V3) 潛在 Done 任務數: {len(task_ids)}")
    
    # 查詢這些任務或流程關聯的變數，找寻 task_auto_complete 或 task_bypass
    q_vars = f"""
    SELECT PROC_INST_ID_, TASK_ID_, NAME_, VAR_TYPE_, TEXT_, LONG_
    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108
    WHERE PROC_INST_ID_ IN {proc_ids}
      AND NAME_ IN ('autoComplete', 'task_auto_complete', 'bypass', 'task_bypass')
    """
    
    df_vars = pd.read_sql(q_vars, conn)
    conn.close()
    
    print("\n--- 找到的可疑排除變數統計 ---")
    if len(df_vars) > 0:
        print(df_vars.groupby(['NAME_', 'VAR_TYPE_', 'TEXT_', 'LONG_']).size().reset_index(name='COUNT').to_string(index=False))
        
        # 配對回任務
        # 流程變數：TASK_ID_ 會是 NULL
        # 任務變數：TASK_ID_ 有值
        bypass_procs = df_vars[(df_vars['NAME_'].isin(['bypass', 'task_bypass'])) | (df_vars['NAME_'] == 'autoComplete') | (df_vars['NAME_'] == 'task_auto_complete')]['PROC_INST_ID_'].unique()
        
        affected_tasks = df_tasks[df_tasks['PROC_INST_ID_'].isin(bypass_procs)]
        print(f"\n受到這些 bypass/autoComplete 變數影響的任務筆數: {len(affected_tasks)}")
        print(f"如果我們剔除這些任務，剩下的完美任務數: {len(task_ids) - len(affected_tasks)} 筆")
        print(f"(距離報表目標 163 筆，還有 {abs((len(task_ids) - len(affected_tasks)) - 163)} 筆差距)")
    else:
        print("沒有找到任何相關的 bypass 或 auto_complete 變數！")

if __name__ == "__main__":
    check_bypass_vars()
