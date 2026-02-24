import pyodbc, pandas as pd, warnings
warnings.filterwarnings("ignore")
conn = pyodbc.connect('DRIVER={SQL Server};SERVER=WJOAUATDB01S.delta.corp,65000;DATABASE=APP_SRV_BPM;UID=APP_SRV_BPM;PWD=APP_SRV_BPM')

# Q1: What TASK_DEF_KEY_ patterns exist for DG3/SMT on 12-25?
q1 = """
SELECT TOP 15 t.TASK_DEF_KEY_, COUNT(*) AS cnt
FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
WHERE CAST(t.START_TIME_ AS DATE) = '2025-12-25'
  AND EXISTS(SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v WHERE v.PROC_INST_ID_=t.PROC_INST_ID_ AND v.NAME_='plant' AND v.TEXT_='DG3')
  AND EXISTS(SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v WHERE v.PROC_INST_ID_=t.PROC_INST_ID_ AND v.NAME_='factory' AND v.TEXT_='SMT')
GROUP BY t.TASK_DEF_KEY_
ORDER BY cnt DESC
"""
print("=== Q1: TASK_DEF_KEY_ for DG3/SMT on 12-25 ===")
print(pd.read_sql(q1, conn).to_string(index=False))

# Q2: What moNumber prefixes exist for DG3/SMT on 12-25?
q2 = """
SELECT TOP 15 LEFT(v_mo.TEXT_, 3) AS mo_prefix, COUNT(*) AS cnt
FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 t
JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v_mo ON v_mo.PROC_INST_ID_=t.PROC_INST_ID_ AND v_mo.NAME_='moNumber'
WHERE CAST(t.START_TIME_ AS DATE) = '2025-12-25'
  AND EXISTS(SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v WHERE v.PROC_INST_ID_=t.PROC_INST_ID_ AND v.NAME_='plant' AND v.TEXT_='DG3')
  AND EXISTS(SELECT 1 FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v WHERE v.PROC_INST_ID_=t.PROC_INST_ID_ AND v.NAME_='factory' AND v.TEXT_='SMT')
GROUP BY LEFT(v_mo.TEXT_, 3)
ORDER BY cnt DESC
"""
print("\n=== Q2: moNumber prefixes for DG3/SMT on 12-25 ===")
print(pd.read_sql(q2, conn).to_string(index=False))

# Q3: Check if lineName filter matters (maybe it's 'line' not 'lineName'?)
q3 = """
SELECT v.NAME_, v.TEXT_, COUNT(*) cnt
FROM APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 v
WHERE v.TEXT_ = 'ST02'
GROUP BY v.NAME_, v.TEXT_
"""
print("\n=== Q3: Variable names where TEXT_='ST02' ===")
print(pd.read_sql(q3, conn).to_string(index=False))

conn.close()
