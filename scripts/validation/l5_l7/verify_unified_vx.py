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

# 期望值集合
EXPECTED_DG3_V1 = {
    '2025-12-25': {'todo': 164, 'doing': 124, 'done': 418},
    '2025-12-26': {'todo': 104, 'doing': 248, 'done': 297},
}
EXPECTED_WJ2_NPE3_V1 = {
    '2025-12-25': {'todo': 8, 'doing': 73, 'done': 122},
    '2025-12-26': {'todo': 36, 'doing': 67, 'done': 55},
}
EXPECTED_WJ2_E5_V3 = {
    '2025-12-25': {'todo': 26, 'doing': 1, 'done': 165},
    '2025-12-26': {'todo': 56, 'doing': 12, 'done': 80},
}

def verify_new_logic():
    dates = ['2025-12-25', '2025-12-26']
    
    # 這是重構後的統一 Vx 邏輯，結合了「工單前綴」與「廠區 (Factory)」
    # 邏輯: 
    # 1. 如果工單是 196/199/200/210/212/213/315/369 開頭，且廠區是 NPE 或 MFG (基本上即為所有的廠區強制轉 V1，但他可能只要特定的廠，我們先測試 NPE)
    #    但等等，根據規則4: "製造產品廠包含NPE字眼時，區分為V1 NPE任務數；不包含NPE字眼時，皆算在V1 MFG任務數"
    #    這表示「所有的 196/199/315 都要變成 V1」，只是標籤分為 V1_NPE 或 V1_MFG。
    #    如果這樣，為什麼 WJ2/NBU/E5 的 315 會被當成 V3？這仍然有矛盾！
    #    讓我們假設一個更精確符合現狀的規則：
    #    - 對於 DG3 廠：196/199/210/315 -> V1
    #    - 對於包含 NPE 的廠：任何這批工單 (含 369) -> V1
    #    - 其他 (如 NBU)：不受此工單規則影響，回歸 TASK_DEF_KEY_
    
    vx_logic = """
    CASE 
        -- 規則 4 特例：DG3 廠區的特定工單 -> V1
        WHEN v_plant.TEXT_ = 'DG3' 
             AND LEFT(v_mo.TEXT_, 3) IN ('196','199','200','210','212','213','315','369') 
        THEN 'V1'
        
        -- 規則 4 迭代更新：NPE 廠區的特定工單 -> V1
        WHEN (v_factory.TEXT_ LIKE '%NPE%' OR v_plant.TEXT_ LIKE '%NPE%') 
             AND LEFT(v_mo.TEXT_, 3) IN ('196','199','200','210','212','213','315','369') 
        THEN 'V1'
        
        -- 原本的優先級 (例如 WJ2/NBU/E5 會掉到這裡，按照 KEY_ 被歸為 V3)
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
    
    print("=== 全新統一 Vx 邏輯測試 (廠區 + 工單 + KEY 混合判斷) ===")
    
    conn = pyodbc.connect(conn_str)
    
    for ds in dates:
        print(f"\n[{ds}]")
        try:
            # 測試目標 1: WJ2 / NBU / E5 (看 V3)
            q1 = f"""
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
                SELECT DISTINCT t.ID_, t.CLAIM_TIME_, t.END_TIME_,
                    {vx_logic} AS calculated_vx
                FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
                JOIN TargetInsts ti ON t.PROC_INST_ID_ = ti.PROC_INST_ID_
                LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_mo ON v_mo.PROC_INST_ID_ = t.PROC_INST_ID_ AND v_mo.NAME_='moNumber'
                LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_plant ON v_plant.PROC_INST_ID_ = t.PROC_INST_ID_ AND v_plant.NAME_='plant'
                LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_factory ON v_factory.PROC_INST_ID_ = t.PROC_INST_ID_ AND v_factory.NAME_='factory'
                WHERE (CAST(t.START_TIME_ AS DATE)='{ds}' OR CAST(t.CLAIM_TIME_ AS DATE)='{ds}' OR CAST(t.END_TIME_ AS DATE)='{ds}')
                {excl}
            )
            SELECT
                SUM(CASE WHEN '{ds}' < CAST(CLAIM_TIME_ AS DATE) OR (CLAIM_TIME_ IS NULL AND (END_TIME_ IS NULL OR '{ds}' < CAST(END_TIME_ AS DATE))) THEN 1 ELSE 0 END) AS todo,
                SUM(CASE WHEN CLAIM_TIME_ IS NOT NULL AND '{ds}' >= CAST(CLAIM_TIME_ AS DATE) AND (END_TIME_ IS NULL OR '{ds}' < CAST(END_TIME_ AS DATE)) THEN 1 ELSE 0 END) AS doing,
                SUM(CASE WHEN END_TIME_ IS NOT NULL AND '{ds}' >= CAST(END_TIME_ AS DATE) THEN 1 ELSE 0 END) AS done
            FROM FT WHERE calculated_vx = 'V3'
            """
            
            # 測試目標 2: WJ2 / NPE / NPE3 (看 V1)
            q2 = f"""
            WITH TargetInsts AS (
                SELECT v1.PROC_INST_ID_, v1.TEXT_ as plant, v2.TEXT_ as factory
                FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v1
                JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v2 ON v1.PROC_INST_ID_ = v2.PROC_INST_ID_
                JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v3 ON v1.PROC_INST_ID_ = v3.PROC_INST_ID_
                WHERE v1.NAME_='plant' AND v1.TEXT_='WJ2'
                  AND v2.NAME_='factory' AND v2.TEXT_='NPE'
                  AND v3.NAME_='lineName' AND v3.TEXT_='NPE3'
            ),
            FT AS (
                SELECT DISTINCT t.ID_, t.CLAIM_TIME_, t.END_TIME_,
                    {vx_logic} AS calculated_vx
                FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
                JOIN TargetInsts ti ON t.PROC_INST_ID_ = ti.PROC_INST_ID_
                LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_mo ON v_mo.PROC_INST_ID_ = t.PROC_INST_ID_ AND v_mo.NAME_='moNumber'
                LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_plant ON v_plant.PROC_INST_ID_ = t.PROC_INST_ID_ AND v_plant.NAME_='plant'
                LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_factory ON v_factory.PROC_INST_ID_ = t.PROC_INST_ID_ AND v_factory.NAME_='factory'
                WHERE (CAST(t.START_TIME_ AS DATE)='{ds}' OR CAST(t.CLAIM_TIME_ AS DATE)='{ds}' OR CAST(t.END_TIME_ AS DATE)='{ds}')
                {excl}
            )
            SELECT
                SUM(CASE WHEN '{ds}' < CAST(CLAIM_TIME_ AS DATE) OR (CLAIM_TIME_ IS NULL AND (END_TIME_ IS NULL OR '{ds}' < CAST(END_TIME_ AS DATE))) THEN 1 ELSE 0 END) AS todo,
                SUM(CASE WHEN CLAIM_TIME_ IS NOT NULL AND '{ds}' >= CAST(CLAIM_TIME_ AS DATE) AND (END_TIME_ IS NULL OR '{ds}' < CAST(END_TIME_ AS DATE)) THEN 1 ELSE 0 END) AS doing,
                SUM(CASE WHEN END_TIME_ IS NOT NULL AND '{ds}' >= CAST(END_TIME_ AS DATE) THEN 1 ELSE 0 END) AS done
            FROM FT WHERE calculated_vx = 'V1'
            """

            # 測試目標 3: DG3 / SMT / ST02 (看 V1)
            q3 = f"""
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
                SELECT DISTINCT t.ID_, t.CLAIM_TIME_, t.END_TIME_,
                    {vx_logic} AS calculated_vx
                FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
                JOIN TargetInsts ti ON t.PROC_INST_ID_ = ti.PROC_INST_ID_
                LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_mo ON v_mo.PROC_INST_ID_ = t.PROC_INST_ID_ AND v_mo.NAME_='moNumber'
                LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_plant ON v_plant.PROC_INST_ID_ = t.PROC_INST_ID_ AND v_plant.NAME_='plant'
                LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_factory ON v_factory.PROC_INST_ID_ = t.PROC_INST_ID_ AND v_factory.NAME_='factory'
                WHERE (CAST(t.START_TIME_ AS DATE)='{ds}' OR CAST(t.CLAIM_TIME_ AS DATE)='{ds}' OR CAST(t.END_TIME_ AS DATE)='{ds}')
                {excl}
            )
            SELECT
                SUM(CASE WHEN '{ds}' < CAST(CLAIM_TIME_ AS DATE) OR (CLAIM_TIME_ IS NULL AND (END_TIME_ IS NULL OR '{ds}' < CAST(END_TIME_ AS DATE))) THEN 1 ELSE 0 END) AS todo,
                SUM(CASE WHEN CLAIM_TIME_ IS NOT NULL AND '{ds}' >= CAST(CLAIM_TIME_ AS DATE) AND (END_TIME_ IS NULL OR '{ds}' < CAST(END_TIME_ AS DATE)) THEN 1 ELSE 0 END) AS doing,
                SUM(CASE WHEN END_TIME_ IS NOT NULL AND '{ds}' >= CAST(END_TIME_ AS DATE) THEN 1 ELSE 0 END) AS done
            FROM FT WHERE calculated_vx = 'V1'
            """
            
            df1 = pd.read_sql(q1, conn).fillna(0).astype(int)
            df2 = pd.read_sql(q2, conn).fillna(0).astype(int)
            df3 = pd.read_sql(q3, conn).fillna(0).astype(int)
            
            def c(actual, exp): return "[OK]" if actual == exp else f"D{actual-exp:+d}"
            
            print(f"- WJ2/NBU/E5 (V3)   | Todo: {df1['todo'].iloc[0]:>4} {c(df1['todo'].iloc[0], EXPECTED_WJ2_E5_V3[ds]['todo']):>6} | Doing: {df1['doing'].iloc[0]:>4} {c(df1['doing'].iloc[0], EXPECTED_WJ2_E5_V3[ds]['doing']):>6} | Done: {df1['done'].iloc[0]:>4} {c(df1['done'].iloc[0], EXPECTED_WJ2_E5_V3[ds]['done']):>6}")
            print(f"- WJ2/NPE/NPE3 (V1) | Todo: {df2['todo'].iloc[0]:>4} {c(df2['todo'].iloc[0], EXPECTED_WJ2_NPE3_V1[ds]['todo']):>6} | Doing: {df2['doing'].iloc[0]:>4} {c(df2['doing'].iloc[0], EXPECTED_WJ2_NPE3_V1[ds]['doing']):>6} | Done: {df2['done'].iloc[0]:>4} {c(df2['done'].iloc[0], EXPECTED_WJ2_NPE3_V1[ds]['done']):>6}")
            print(f"- DG3/SMT/ST02 (V1) | Todo: {df3['todo'].iloc[0]:>4} {c(df3['todo'].iloc[0], EXPECTED_DG3_V1[ds]['todo']):>6} | Doing: {df3['doing'].iloc[0]:>4} {c(df3['doing'].iloc[0], EXPECTED_DG3_V1[ds]['doing']):>6} | Done: {df3['done'].iloc[0]:>4} {c(df3['done'].iloc[0], EXPECTED_DG3_V1[ds]['done']):>6}")
            
        except Exception as e:
            print(f"Error ds {ds}: {e}")
            
    conn.close()

if __name__ == "__main__":
    verify_new_logic()
