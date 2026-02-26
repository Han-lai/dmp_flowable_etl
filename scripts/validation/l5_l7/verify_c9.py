import pyodbc
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'
conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'

EXPECTED_V3_C9 = {
    "2025-12-25": {"total": 145, "todo": 16, "doing": 12, "done": 117},
    "2025-12-26": {"total": 50, "todo": 11, "doing": 0, "done": 39},
    "2025-12-27": {"total": 74, "todo": 25, "doing": 5, "done": 44},
    "2025-12-28": {"total": 1, "todo": 1, "doing": 0, "done": 0},
    "2025-12-29": {"total": 114, "todo": 14, "doing": 6, "done": 94},
    "2025-12-30": {"total": 89, "todo": 9, "doing": 0, "done": 80},
    "2025-12-31": {"total": 34, "todo": 10, "doing": 0, "done": 24}
}

def verify_c9():
    vx_logic = """
    CASE 
        WHEN v_plant.TEXT_ = 'DG3' 
             AND LEFT(v_mo.TEXT_, 3) IN ('196','199','200','210','212','213','315','369') THEN 'V1'
        WHEN (v_factory.TEXT_ LIKE '%NPE%' OR v_plant.TEXT_ LIKE '%NPE%') 
             AND LEFT(v_mo.TEXT_, 3) IN ('196','199','200','210','212','213','315','369') THEN 'V1'
        WHEN t.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
        WHEN t.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
        WHEN t.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
        ELSE 'Unknown'
    END
    """
    
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

    q = f"""
    WITH TargetInsts AS (
        SELECT v1.PROC_INST_ID_{", v1.TEXT_ as plant, v2.TEXT_ as factory" if True else ""}
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v1
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v2 ON v1.PROC_INST_ID_ = v2.PROC_INST_ID_
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v3 ON v1.PROC_INST_ID_ = v3.PROC_INST_ID_
        WHERE v1.NAME_='plant' AND v1.TEXT_='WJ2'
          AND v2.NAME_='factory' AND v2.TEXT_='NBJ'
          AND v3.NAME_='lineName' AND v3.TEXT_='C9'
    ),
    FT AS (
        SELECT DISTINCT t.ID_, t.NAME_, t.TASK_DEF_KEY_, t.DELETE_REASON_, t.DURATION_, 
               CAST(t.START_TIME_ AS DATE) as start_date, 
               CAST(t.CLAIM_TIME_ AS DATE) as claim_date, 
               CAST(t.END_TIME_ AS DATE) as end_date,
            {vx_logic} AS calculated_vx
        FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
        JOIN TargetInsts ti ON t.PROC_INST_ID_ = ti.PROC_INST_ID_
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_mo ON v_mo.PROC_INST_ID_ = t.PROC_INST_ID_ AND v_mo.NAME_='moNumber'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_plant ON v_plant.PROC_INST_ID_ = t.PROC_INST_ID_ AND v_plant.NAME_='plant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_factory ON v_factory.PROC_INST_ID_ = t.PROC_INST_ID_ AND v_factory.NAME_='factory'
        WHERE (CAST(t.START_TIME_ AS DATE) >= '2025-12-25' AND CAST(t.START_TIME_ AS DATE) <= '2025-12-31')
           OR (CAST(t.CLAIM_TIME_ AS DATE) >= '2025-12-25' AND CAST(t.CLAIM_TIME_ AS DATE) <= '2025-12-31')
           OR (CAST(t.END_TIME_ AS DATE) >= '2025-12-25' AND CAST(t.END_TIME_ AS DATE) <= '2025-12-31')
        {excl}
    )
    SELECT * FROM FT 
    """
    
    conn = pyodbc.connect(conn_str)
    df = pd.read_sql(q, conn)
    conn.close()
    
    df_v3 = df[df['calculated_vx'] == 'V3']
    
    dates = pd.date_range(start='2025-12-25', end='2025-12-31')
    
    print("================== WJ2 / NBJ / C9 (V3) ==================")
    print("日期       | 欄位  | QAS 資料 | 報表期望 | 差異")
    print("-" * 55)
    
    has_any_diff = False
    for d in reversed(dates):
        ds = d.strftime('%Y-%m-%d')
        exp = EXPECTED_V3_C9[ds]
        
        # 依照規則計算
        total = len(df_v3[(df_v3['start_date'] == ds) | (df_v3['claim_date'] == ds) | (df_v3['end_date'] == ds)])
        todo = len(df_v3[
            ((df_v3['start_date'] == ds) | (df_v3['claim_date'] == ds) | (df_v3['end_date'] == ds)) &
            ((df_v3['claim_date'] > ds) | (df_v3['claim_date'].isna() & (df_v3['end_date'].isna() | (df_v3['end_date'] > ds))))
        ])
        doing = len(df_v3[
            ((df_v3['start_date'] == ds) | (df_v3['claim_date'] == ds) | (df_v3['end_date'] == ds)) &
            (df_v3['claim_date'].notna() & (df_v3['claim_date'] <= ds) & (df_v3['end_date'].isna() | (df_v3['end_date'] > ds)))
        ])
        done = len(df_v3[
            ((df_v3['start_date'] == ds) | (df_v3['claim_date'] == ds) | (df_v3['end_date'] == ds)) &
            (df_v3['end_date'].notna() & (df_v3['end_date'] <= ds))
        ])
        
        qas = {'total': total, 'todo': todo, 'doing': doing, 'done': done}
        for field in ['total', 'todo', 'doing', 'done']:
            diff = qas[field] - exp[field]
            if diff != 0:
                has_any_diff = True
                print(f"{ds} | {field:<5} | {qas[field]:<8} | {exp[field]:<8} | {diff:+d}")
                
    if not has_any_diff:
        print("所有指標 100% 完美吻合！")

if __name__ == "__main__":
    verify_c9()
