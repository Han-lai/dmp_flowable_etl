import pyodbc, pandas as pd, warnings
warnings.filterwarnings("ignore")
conn = pyodbc.connect('DRIVER={SQL Server};SERVER=WJOAUATDB01S.delta.corp,65000;DATABASE=APP_SRV_BPM;UID=APP_SRV_BPM;PWD=APP_SRV_BPM')

print("=== Q1: TASK_DEF_KEY_ for WJ2/NBU/E5 on 12-25 ===")
q1 = """
SELECT TOP 15 t.TASK_DEF_KEY_, COUNT(*) cnt
FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
WHERE CAST(t.START_TIME_ AS DATE) = '2025-12-25'
  AND EXISTS(SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v WHERE v.PROC_INST_ID_=t.PROC_INST_ID_ AND v.NAME_='plant' AND v.TEXT_='WJ2')
  AND EXISTS(SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v WHERE v.PROC_INST_ID_=t.PROC_INST_ID_ AND v.NAME_='factory' AND v.TEXT_='NBU')
  AND EXISTS(SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v WHERE v.PROC_INST_ID_=t.PROC_INST_ID_ AND v.NAME_='lineCode' AND v.TEXT_='E5')
GROUP BY t.TASK_DEF_KEY_ ORDER BY cnt DESC
"""
df1 = pd.read_sql(q1, conn)
if df1.empty:
    print("Wait, checking 'lineName' instead of 'lineCode'")
    q1_alt = q1.replace("'lineCode'", "'lineName'")
    df1 = pd.read_sql(q1_alt, conn)
print(df1.to_string(index=False))

print("\n=== Q2: moNumber prefixes for WJ2/NBU/E5 on 12-25 ===")
q2 = """
SELECT TOP 15 LEFT(v_mo.TEXT_, 3) AS mo_prefix, COUNT(*) cnt
FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_mo ON v_mo.PROC_INST_ID_=t.PROC_INST_ID_ AND v_mo.NAME_='moNumber'
WHERE CAST(t.START_TIME_ AS DATE) = '2025-12-25'
  AND EXISTS(SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v WHERE v.PROC_INST_ID_=t.PROC_INST_ID_ AND v.NAME_='plant' AND v.TEXT_='WJ2')
  AND EXISTS(SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v WHERE v.PROC_INST_ID_=t.PROC_INST_ID_ AND v.NAME_='factory' AND v.TEXT_='NBU')
  AND EXISTS(SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v WHERE v.PROC_INST_ID_=t.PROC_INST_ID_ AND v.NAME_='lineCode' AND v.TEXT_='E5')
GROUP BY LEFT(v_mo.TEXT_, 3) ORDER BY cnt DESC
"""
df2 = pd.read_sql(q2, conn)
if df2.empty:
     df2 = pd.read_sql(q2.replace("'lineCode'", "'lineName'"), conn)
print(df2.to_string(index=False))

conn.close()
