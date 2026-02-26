import pyodbc
import pandas as pd
import warnings
import sys
import clickhouse_connect

warnings.filterwarnings("ignore")

server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'
database = 'APP_SRV_BPM'
conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'

ch_client = clickhouse_connect.get_client(host='10.136.218.207', port=8121, username='default', password='default')

vx_logic = """
CASE 
    WHEN v_plant.TEXT_ = 'DG3' 
         AND LEFT(v_mo.TEXT_, 3) IN ('196','199','200','210','212','213','315') THEN 'V1'
    WHEN (v_factory.TEXT_ LIKE '%NPE%' OR v_plant.TEXT_ LIKE '%NPE%') 
         AND LEFT(v_mo.TEXT_, 3) IN ('196','199','200','210','212','213','315') THEN 'V1'
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

def get_qas_data(plant, factory, line):
    conn = pyodbc.connect(conn_str)
    
    q = f"""
    WITH TargetInsts AS (
        SELECT v1.PROC_INST_ID_, v1.TEXT_ as plant, v2.TEXT_ as factory
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v1
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v2 ON v1.PROC_INST_ID_ = v2.PROC_INST_ID_
        JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v3 ON v1.PROC_INST_ID_ = v3.PROC_INST_ID_
        WHERE v1.NAME_='plant' AND v1.TEXT_='{plant}'
          AND v2.NAME_='factory' AND v2.TEXT_='{factory}'
          AND v3.NAME_='lineName' AND v3.TEXT_='{line}'
    ),
    FT AS (
        SELECT DISTINCT t.ID_, t.CLAIM_TIME_, t.END_TIME_, CAST(t.START_TIME_ AS DATE) as start_date,
               CAST(t.CLAIM_TIME_ AS DATE) as claim_date, CAST(t.END_TIME_ AS DATE) as end_date,
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
    df = pd.read_sql(q, conn)
    conn.close()
    return df

def aggregate_qas_data(df, ds, vx_type):
    df_vx = df[df['calculated_vx'] == vx_type]
    
    total = len(df_vx[(df_vx['start_date'] == ds) | (df_vx['claim_date'] == ds) | (df_vx['end_date'] == ds)])
    
    todo = len(df_vx[
        ((df_vx['start_date'] == ds) | (df_vx['claim_date'] == ds) | (df_vx['end_date'] == ds)) &
        ((df_vx['claim_date'] > ds) | (df_vx['claim_date'].isna() & (df_vx['end_date'].isna() | (df_vx['end_date'] > ds))))
    ])
    
    doing = len(df_vx[
        ((df_vx['start_date'] == ds) | (df_vx['claim_date'] == ds) | (df_vx['end_date'] == ds)) &
        (df_vx['claim_date'].notna() & (df_vx['claim_date'] <= ds) & (df_vx['end_date'].isna() | (df_vx['end_date'] > ds)))
    ])
    
    done = len(df_vx[
        ((df_vx['start_date'] == ds) | (df_vx['claim_date'] == ds) | (df_vx['end_date'] == ds)) &
        (df_vx['end_date'].notna() & (df_vx['end_date'] <= ds))
    ])
    
    return {"total": total, "todo": todo, "doing": doing, "done": done}

def get_clickhouse_data(region, plant, factory, line, vx_type, ds):
    q = f"""
    SELECT 
        sum(total_task) as total,
        sum(todo) as todo,
        sum(doing) as doing,
        sum(done) as done
    FROM gold.rmv_l5_task_completion_v2
    WHERE region='{region}' AND plant='{plant}' AND factory='{factory}' AND line='{line}' 
      AND vx_type='{vx_type}' AND snapshot_date='{ds}'
    """
    res = ch_client.query(q).result_rows[0]
    return {
        "total": int(res[0] or 0),
        "todo": int(res[1] or 0),
        "doing": int(res[2] or 0),
        "done": int(res[3] or 0)
    }

def process_scope(title, plant, factory, line, region, vx_type):
    print(f"Fetching {title}...")
    df_qas = get_qas_data(plant, factory, line)
    
    dates = pd.date_range(start='2025-12-25', end='2025-12-31')
    diff_rows = []
    has_diff = False
    
    for d in reversed(dates):
        ds = d.strftime('%Y-%m-%d')
        qas = aggregate_qas_data(df_qas, ds, vx_type)
        ch = get_clickhouse_data(region, plant, factory, line, vx_type, ds)
        
        fields = ['total', 'todo', 'doing', 'done']
        
        for field in fields:
            qas_val = qas.get(field, 0)
            ch_val = ch.get(field, 0)
            if qas_val != ch_val:
                has_diff = True
                diff_rows.append(f"| {ds} | {field.capitalize()} | {qas_val} | {ch_val} | {ch_val - qas_val:+d} |")
                
    with open('output_live_diff.md', 'a', encoding='utf-8') as f:
        f.write(f"### {title}\n")
        if has_diff:
            f.write("| 日期 | 不符欄位 | QAS 資料值 | 金層實際提供值 | 差異 |\n")
            f.write("|---|---|---|---|---|\n")
            for r in diff_rows:
                f.write(r + "\n")
        else:
            f.write("**結果：完美吻合！ (100% Match)**\n")
        f.write("\n")

def main():
    with open('output_live_diff.md', 'w', encoding='utf-8') as f:
        f.write("## 最新 Gold 層同步驗證差異報告\n\n")

    process_scope("V1 / CNS / DG3 / SMT / ST02", "DG3", "SMT", "ST02", "CNS", "V1")
    process_scope("V3 / CNS / DG3 / SMT / ST02", "DG3", "SMT", "ST02", "CNS", "V3")
    process_scope("V3 / CNE / WJ2 / NBU / E5", "WJ2", "NBU", "E5", "CNE", "V3")
    process_scope("V1 / CNE / WJ2 / NPE / NPE3", "WJ2", "NPE", "NPE3", "CNE", "V1")
    print("Done. Wrote output_live_diff.md")

if __name__ == "__main__":
    main()
