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

EXPECTED_V1_DG3 = {
    "2025-12-25": {"total": 3555, "todo": 3, "doing": 179, "done": 3373, "acc": 182},
    "2025-12-26": {"total": 198, "todo": 44, "doing": 69, "done": 85, "acc": 113},
    "2025-12-27": {"total": 687, "todo": 23, "doing": 67, "done": 597, "acc": 90},
    "2025-12-28": {"total": 412, "todo": 13, "doing": 78, "done": 321, "acc": 91},
    "2025-12-29": {"total": 49, "todo": 3, "doing": 8, "done": 38, "acc": 65},
    "2025-12-30": {"total": 127, "todo": 7, "doing": 53, "done": 67, "acc": 99},
    "2025-12-31": {"total": 147, "todo": 64, "doing": 28, "done": 55, "acc": 132}
}

EXPECTED_V3_DG3 = {
    "2025-12-25": {"total": 265, "todo": 66, "doing": 36, "done": 163, "acc": 154},
    "2025-12-26": {"total": 176, "todo": 19, "doing": 66, "done": 91, "acc": 171},
    "2025-12-27": {"total": 235, "todo": 22, "doing": 29, "done": 184, "acc": 94},
    "2025-12-28": {"total": 12, "todo": 1, "doing": 1, "done": 10, "acc": 90},
    "2025-12-29": {"total": 147, "todo": 64, "doing": 28, "done": 55, "acc": 132},
    "2025-12-30": {"total": 127, "todo": 7, "doing": 53, "done": 67, "acc": 99},
    "2025-12-31": {"total": 49, "todo": 3, "doing": 8, "done": 38, "acc": 65}
}

EXPECTED_V3_E5 = {
    "2025-12-25": {"total": 192, "todo": 26, "doing": 1, "done": 165, "acc": 40},
    "2025-12-26": {"total": 148, "todo": 56, "doing": 12, "done": 80, "acc": 76},
    "2025-12-27": {"total": 110, "todo": 14, "doing": 4, "done": 92, "acc": 44},
    "2025-12-28": {"total": 11, "todo": 3, "doing": 0, "done": 8, "acc": 46},
    "2025-12-29": {"total": 88, "todo": 3, "doing": 22, "done": 63, "acc": 40},
    "2025-12-30": {"total": 262, "todo": 8, "doing": 60, "done": 194, "acc": 95},
    "2025-12-31": {"total": 210, "todo": 9, "doing": 5, "done": 196, "acc": 97}
}

EXPECTED_V1_NPE3 = {
    "2025-12-25": {"total": 203, "todo": 8, "doing": 73, "done": 122, "acc": 222},
    "2025-12-26": {"total": 158, "todo": 36, "doing": 67, "done": 55, "acc": 285},
    "2025-12-27": {"total": 69, "todo": 5, "doing": 30, "done": 34, "acc": 274},
    "2025-12-28": {"total": 2, "todo": 2, "doing": 0, "done": 0, "acc": 271},
    "2025-12-29": {"total": 123, "todo": 0, "doing": 41, "done": 82, "acc": 272},
    "2025-12-30": {"total": 237, "todo": 118, "doing": 44, "done": 75, "acc": 347},
    "2025-12-31": {"total": 243, "todo": 2, "doing": 129, "done": 112, "acc": 316}
}

# The user explicitly said NO 369
# And mapping rules from the prompt
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

def aggregate_data(df, ds, vx_type):
    df_vx = df[df['calculated_vx'] == vx_type]
    
    # Total Task
    total = len(df_vx[(df_vx['start_date'] == ds) | (df_vx['claim_date'] == ds) | (df_vx['end_date'] == ds)])
    
    # Todo
    todo = len(df_vx[
        ((df_vx['start_date'] == ds) | (df_vx['claim_date'] == ds) | (df_vx['end_date'] == ds)) &
        ((df_vx['claim_date'] > ds) | (df_vx['claim_date'].isna() & (df_vx['end_date'].isna() | (df_vx['end_date'] > ds))))
    ])
    
    # Doing
    doing = len(df_vx[
        ((df_vx['start_date'] == ds) | (df_vx['claim_date'] == ds) | (df_vx['end_date'] == ds)) &
        (df_vx['claim_date'].notna() & (df_vx['claim_date'] <= ds) & (df_vx['end_date'].isna() | (df_vx['end_date'] > ds)))
    ])
    
    # Done
    done = len(df_vx[
        ((df_vx['start_date'] == ds) | (df_vx['claim_date'] == ds) | (df_vx['end_date'] == ds)) &
        (df_vx['end_date'].notna() & (df_vx['end_date'] <= ds))
    ])
    
    return {"total": total, "todo": todo, "doing": doing, "done": done}

def print_diffs(title, expected, df, vx_type):
    from sys import stdout
    dates = pd.date_range(start='2025-12-25', end='2025-12-31')
    diff_rows = []
    has_diff = False
    
    for d in reversed(dates):
        ds = d.strftime('%Y-%m-%d')
        exp = expected.get(ds, {})
        if not exp:
            continue
            
        qas = aggregate_data(df, ds, vx_type)
        
        # Check diff explicitly
        fields = ['total', 'todo', 'doing', 'done']
        
        for field in fields:
            exp_val = exp.get(field, 0)
            qas_val = qas.get(field, 0)
            if exp_val != qas_val:
                has_diff = True
                diff_rows.append(f"| {ds} | {field.capitalize()} | {qas_val} | {exp_val} | {qas_val - exp_val:+d} |")
                
    with open('output_final_diff.md', 'a', encoding='utf-8') as f:
        f.write(f"### {title}\n")
        if has_diff:
            f.write("| 日期 | 不符欄位 | QAS 資料值 | 實際提供值 | 差異 |\n")
            f.write("|---|---|---|---|---|\n")
            for r in diff_rows:
                f.write(r + "\n")
        else:
            f.write("**結果：完美吻合！ (100% Match)**\n")
        f.write("\n")

def main():
    with open('output_final_diff.md', 'w', encoding='utf-8') as f:
        f.write("## 統一邏輯驗證差異報告\n\n")

    # 1. DG3 / SMT / ST02
    print("Fetching DG3/SMT/ST02...")
    df_dg3 = get_qas_data('DG3', 'SMT', 'ST02')
    print_diffs("V1 / CNS / DG3 / SMT / ST02", EXPECTED_V1_DG3, df_dg3, 'V1')
    print_diffs("V3 / CNS / DG3 / SMT / ST02", EXPECTED_V3_DG3, df_dg3, 'V3')
    
    # 2. WJ2 / NBU / E5
    print("Fetching WJ2/NBU/E5...")
    df_e5 = get_qas_data('WJ2', 'NBU', 'E5')
    print_diffs("V3 / CNE / WJ2 / NBU / E5", EXPECTED_V3_E5, df_e5, 'V3')
    
    # 3. WJ2 / NPE / NPE3
    print("Fetching WJ2/NPE/NPE3...")
    df_npe3 = get_qas_data('WJ2', 'NPE', 'NPE3')
    print_diffs("V1 / CNE / WJ2 / NPE / NPE3", EXPECTED_V1_NPE3, df_npe3, 'V1')
    print("Done. Wrote output_final_diff.md")

if __name__ == "__main__":
    main()
