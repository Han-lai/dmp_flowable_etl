import pyodbc
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'
conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'

def diag_e5():
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
          AND v2.NAME_='factory' AND v2.TEXT_='NBU'
          AND v3.NAME_='lineName' AND v3.TEXT_='E5'
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
    
    dates = pd.date_range(start='2025-12-25', end='2025-12-31')
    
    # === V3 分析 ===
    print("================== WJ2 / NBU / E5 (V3) ==================")
    df_v3 = df[df['calculated_vx'] == 'V3']
    for d in reversed(dates):
        ds = d.strftime('%Y-%m-%d')
        df_done = df_v3[
            ((df_v3['start_date'] == ds) | (df_v3['claim_date'] == ds) | (df_v3['end_date'] == ds)) &
            (df_v3['end_date'].notna() & (df_v3['end_date'] <= ds))
        ]
        if len(df_done) > 0:
            print(f"[{ds}] V3 Done: {len(df_done)}")
    
    # 深入分析 12-25 的 V3 Done (先前發現有 169 筆 QAS vs 165 筆期望，差了 4 筆)
    df_done_v3_25 = df_v3[
        ((df_v3['start_date'] == '2025-12-25') | (df_v3['claim_date'] == '2025-12-25') | (df_v3['end_date'] == '2025-12-25')) &
        (df_v3['end_date'].notna() & (df_v3['end_date'] <= '2025-12-25'))
    ]
    print(f"\n--- 12-25 V3 Done (QAS={len(df_done_v3_25)}) 任務名稱分佈 ---")
    print(df_done_v3_25['NAME_'].value_counts().to_string())
    
    # === V1 分析 ===
    print("\n\n================== WJ2 / NBU / E5 (V1) ==================")
    df_v1 = df[df['calculated_vx'] == 'V1']
    for d in reversed(dates):
        ds = d.strftime('%Y-%m-%d')
        df_done = df_v1[
            ((df_v1['start_date'] == ds) | (df_v1['claim_date'] == ds) | (df_v1['end_date'] == ds)) &
            (df_v1['end_date'].notna() & (df_v1['end_date'] <= ds))
        ]
        if len(df_done) > 0:
            print(f"[{ds}] V1 Done: {len(df_done)}")
            
    # 深入分析 V1 任務 (看看到底是哪些任務被判斷成了 V1)
    if len(df_v1) > 0:
        print(f"\n--- WJ2/NBU/E5 (V1) 總計 {len(df_v1)} 筆關聯紀錄的任務金鑰分佈 ---")
        print(df_v1['TASK_DEF_KEY_'].value_counts().to_string())
    else:
        print("\nWJ2/NBU/E5 完全沒有被歸類為 V1 的任務紀錄。")

if __name__ == "__main__":
    diag_e5()
