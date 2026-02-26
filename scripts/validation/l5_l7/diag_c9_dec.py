import pyodbc
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'
conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'

def diag_c9_dec():
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
        SELECT v1.PROC_INST_ID_, v1.TEXT_ as plant, v2.TEXT_ as factory
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
        WHERE (CAST(t.START_TIME_ AS DATE) >= '2025-12-01' AND CAST(t.START_TIME_ AS DATE) <= '2025-12-31')
           OR (CAST(t.CLAIM_TIME_ AS DATE) >= '2025-12-01' AND CAST(t.CLAIM_TIME_ AS DATE) <= '2025-12-31')
           OR (CAST(t.END_TIME_ AS DATE) >= '2025-12-01' AND CAST(t.END_TIME_ AS DATE) <= '2025-12-31')
        {excl}
    )
    SELECT * FROM FT 
    """
    
    conn = pyodbc.connect(conn_str)
    df = pd.read_sql(q, conn)
    conn.close()
    
    dates = pd.date_range(start='2025-12-01', end='2025-12-31')
    
    print("================== WJ2 / NBJ / C9 (V3) 12月份報表 ==================")
    df_v3 = df[df['calculated_vx'] == 'V3']
    
    results = []
    
    for d in dates:
        ds = d.strftime('%Y-%m-%d')
        # 依照先前的標準邏輯：END_TIME <= 當日，且任務在此區間有任一時間節點交互
        df_done = df_v3[
            ((df_v3['start_date'] == ds) | (df_v3['claim_date'] == ds) | (df_v3['end_date'] == ds)) &
            (df_v3['end_date'].notna() & (df_v3['end_date'] <= ds))
        ]
        
        # 純粹的 當日 DONE 統計 (不受限於事件交集，只要這天完成就算)
        df_end_today = df_v3[
            (df_v3['end_date'] == ds) & (df_v3['end_date'].notna())
        ]
        
        if len(df_done) > 0 or len(df_end_today) > 0:
            results.append((ds, len(df_done), len(df_end_today)))
            
    print("日期       | (腳本邏輯) 累積交集驗證 | (真實行為) 當日有 End_Time 的筆數")
    for ds, done_count, end_today in results:
        print(f"{ds} | {done_count:<21} | {end_today}")
        
    # Task key and Name breakdown for the month
    df_v3_dec = df_v3[df_v3['end_date'].between('2025-12-01', '2025-12-31')]
    if len(df_v3_dec) > 0:
        print(f"\n--- 12月份這條線 (C9) V3 所有完成的 {len(df_v3_dec)} 筆 任務名稱排名 ---")
        print(df_v3_dec['NAME_'].value_counts().head(12).to_string())
        
        # 看看有多少筆是大於 1 小時才按掉的
        df_v3_dec['DURATION_MINS'] = df_v3_dec['DURATION_'] / 1000 / 60
        long_tasks = len(df_v3_dec[df_v3_dec['DURATION_MINS'] >= 60])
        print(f"\n其中耗時 > 1 小時的任務筆數: {long_tasks}")
    else:
        print("\n這條線在 12 月份沒有任何符合條件的 V3 完成紀錄。")

if __name__ == "__main__":
    diag_c9_dec()
