import pyodbc
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'
conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'

def diag_done():
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

    ds = '2025-12-25'

    q = f"""
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
        WHERE (CAST(t.START_TIME_ AS DATE)='{ds}' OR CAST(t.CLAIM_TIME_ AS DATE)='{ds}' OR CAST(t.END_TIME_ AS DATE)='{ds}')
        {excl}
    )
    SELECT * FROM FT 
    """
    
    conn = pyodbc.connect(conn_str)
    df = pd.read_sql(q, conn)
    conn.close()
    
    df_vx = df[df['calculated_vx'] == 'V3']
    
    # 按照 verify_final_4_lines.py 的 Pandas Done 邏輯過濾
    df_done = df_vx[
        ((df_vx['start_date'] == ds) | (df_vx['claim_date'] == ds) | (df_vx['end_date'] == ds)) &
        (df_vx['end_date'].notna() & (df_vx['end_date'] <= ds))
    ]
    
    print(f"總共撈出 DG3/SMT/ST02 (V3) 在 {ds} 的 Done 任務數: {len(df_done)} 筆")
    print(f"(報表期望值: 163 筆, 差異: {len(df_done) - 163} 筆)\n")
    
    print("--- 任務名稱 (NAME_) 分佈統計 ---")
    print(df_done['NAME_'].value_counts().to_string())
    
    print("\n--- 任務金鑰 (TASK_DEF_KEY_) 分佈統計 ---")
    print(df_done['TASK_DEF_KEY_'].value_counts().to_string())
    
    print("\n--- DELETE_REASON_ 分佈統計 ---")
    print(df_done['DELETE_REASON_'].value_counts(dropna=False).to_string())

if __name__ == "__main__":
    diag_done()
