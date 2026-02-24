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

print("WJ2 / NPE / NPE3 的原始任務金鑰與 moNumber 統計 (12-25 ~ 12-31)")
conn = pyodbc.connect(conn_str)
q = """
WITH TargetInsts AS (
    SELECT v1.PROC_INST_ID_
    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v1
    JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v2 ON v1.PROC_INST_ID_ = v2.PROC_INST_ID_
    JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v3 ON v1.PROC_INST_ID_ = v3.PROC_INST_ID_
    WHERE v1.NAME_='plant' AND v1.TEXT_='WJ2'
      AND v2.NAME_='factory' AND v2.TEXT_='NPE'
      AND v3.NAME_='lineName' AND v3.TEXT_='NPE3'
)
SELECT 
    LEFT(t.TASK_DEF_KEY_, 4) as TaskKey_Prefix,
    COUNT(DISTINCT t.ID_) as TaskCount
FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
JOIN TargetInsts ti ON t.PROC_INST_ID_ = ti.PROC_INST_ID_
WHERE CAST(t.START_TIME_ AS DATE) >= '2025-12-25' AND CAST(t.START_TIME_ AS DATE) <= '2025-12-31'
GROUP BY LEFT(t.TASK_DEF_KEY_, 4)
"""
df = pd.read_sql(q, conn)
print("\n--- 1. TASK_DEF_KEY_ 統計 ---")
print(df.to_string(index=False))

q2 = """
WITH TargetInsts AS (
    SELECT v1.PROC_INST_ID_
    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v1
    JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v2 ON v1.PROC_INST_ID_ = v2.PROC_INST_ID_
    JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v3 ON v1.PROC_INST_ID_ = v3.PROC_INST_ID_
    WHERE v1.NAME_='plant' AND v1.TEXT_='WJ2'
      AND v2.NAME_='factory' AND v2.TEXT_='NPE'
      AND v3.NAME_='lineName' AND v3.TEXT_='NPE3'
)
SELECT 
    LEFT(v_mo.TEXT_, 3) as moPrefix,
    COUNT(DISTINCT t.ID_) as TaskCount
FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
JOIN TargetInsts ti ON t.PROC_INST_ID_ = ti.PROC_INST_ID_
JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_mo ON v_mo.PROC_INST_ID_ = t.PROC_INST_ID_ AND v_mo.NAME_='moNumber'
WHERE CAST(t.START_TIME_ AS DATE) >= '2025-12-25' AND CAST(t.START_TIME_ AS DATE) <= '2025-12-31'
GROUP BY LEFT(v_mo.TEXT_, 3)
ORDER BY TaskCount DESC
"""
df2 = pd.read_sql(q2, conn)
print("\n--- 2. moNumber 前綴統計 ---")
print(df2.to_string(index=False))
conn.close()
