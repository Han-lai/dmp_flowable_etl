#!/usr/bin/env python3
"""最終驗證"""
import pymssql

conn = pymssql.connect(
    server='twtpesqldv2.delta.corp',
    port='1433',
    user='DMP_APP_SRV',
    password='APP@DB#01',
    database='APP_SRV_BPM'
)
cursor = conn.cursor()

print("=" * 80)
print("最終驗證 - V1 + CNE + WJ2 + NBU + E5")
print("=" * 80)

# 檢查 V1 + WJ2 + NBU + E5 (不含 region)
print("\n1. V1 + WJ2 + NBU + E5 (不含 region):")
cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ = 'moNumber'
        GROUP BY PROC_INST_ID_
    )
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN LOWER(t.TaskStatus) = 'todo' THEN 1 ELSE 0 END) as todo,
        SUM(CASE WHEN LOWER(t.TaskStatus) = 'doing' THEN 1 ELSE 0 END) as doing,
        SUM(CASE WHEN LOWER(t.TaskStatus) = 'done' THEN 1 ELSE 0 END) as done
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
    LEFT JOIN varinst_pivoted v ON t.ProcessInstanceId = v.PROC_INST_ID_
    WHERE t.TaskCreateDate >= '2025-12-01' 
      AND t.TaskCreateDate < '2026-01-01'
      AND t.TaskBypass = 'N'
      AND t.TaskDefinitionKey NOT LIKE 'E%'
      AND t.TaskDefinitionKey NOT LIKE 'C%'
      AND (
          t.TaskDefinitionKey LIKE 'V1%'
          OR v.moNumber LIKE '196%' OR v.moNumber LIKE '199%' OR v.moNumber LIKE '200%'
          OR v.moNumber LIKE '210%' OR v.moNumber LIKE '212%' OR v.moNumber LIKE '213%'
          OR v.moNumber LIKE '315%'
      )
      AND t.Plant = 'WJ2'
      AND t.Factory = 'NBU'
      AND t.Line = 'E5'
""")
row = cursor.fetchone()
print(f"   Total: {row[0]}, TODO: {row[1]}, DOING: {row[2]}, DONE: {row[3]}")

# 檢查這 21 筆的 region 分布
print("\n2. V1 + WJ2 + NBU + E5 的 region 分布:")
cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('moNumber', 'region')
        GROUP BY PROC_INST_ID_
    )
    SELECT v.region, COUNT(*) as cnt
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
    LEFT JOIN varinst_pivoted v ON t.ProcessInstanceId = v.PROC_INST_ID_
    WHERE t.TaskCreateDate >= '2025-12-01' 
      AND t.TaskCreateDate < '2026-01-01'
      AND t.TaskBypass = 'N'
      AND t.TaskDefinitionKey NOT LIKE 'E%'
      AND t.TaskDefinitionKey NOT LIKE 'C%'
      AND (
          t.TaskDefinitionKey LIKE 'V1%'
          OR v.moNumber LIKE '196%' OR v.moNumber LIKE '199%' OR v.moNumber LIKE '200%'
          OR v.moNumber LIKE '210%' OR v.moNumber LIKE '212%' OR v.moNumber LIKE '213%'
          OR v.moNumber LIKE '315%'
      )
      AND t.Plant = 'WJ2'
      AND t.Factory = 'NBU'
      AND t.Line = 'E5'
    GROUP BY v.region
""")
for row in cursor.fetchall():
    print(f"   {row[0]}: {row[1]}")

# 加上 region = CNE
print("\n3. V1 + WJ2 + NBU + E5 + region = CNE:")
cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('moNumber', 'region')
        GROUP BY PROC_INST_ID_
    )
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN LOWER(t.TaskStatus) = 'todo' THEN 1 ELSE 0 END) as todo,
        SUM(CASE WHEN LOWER(t.TaskStatus) = 'doing' THEN 1 ELSE 0 END) as doing,
        SUM(CASE WHEN LOWER(t.TaskStatus) = 'done' THEN 1 ELSE 0 END) as done
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
    LEFT JOIN varinst_pivoted v ON t.ProcessInstanceId = v.PROC_INST_ID_
    WHERE t.TaskCreateDate >= '2025-12-01' 
      AND t.TaskCreateDate < '2026-01-01'
      AND t.TaskBypass = 'N'
      AND t.TaskDefinitionKey NOT LIKE 'E%'
      AND t.TaskDefinitionKey NOT LIKE 'C%'
      AND (
          t.TaskDefinitionKey LIKE 'V1%'
          OR v.moNumber LIKE '196%' OR v.moNumber LIKE '199%' OR v.moNumber LIKE '200%'
          OR v.moNumber LIKE '210%' OR v.moNumber LIKE '212%' OR v.moNumber LIKE '213%'
          OR v.moNumber LIKE '315%'
      )
      AND t.Plant = 'WJ2'
      AND t.Factory = 'NBU'
      AND t.Line = 'E5'
      AND v.region = 'CNE'
""")
row = cursor.fetchone()
print(f"   Total: {row[0]}, TODO: {row[1]}, DOING: {row[2]}, DONE: {row[3]}")

print("\n預期結果:")
print("   Total: 14, TODO: 11, DOING: 2, DONE: 1")

conn.close()
