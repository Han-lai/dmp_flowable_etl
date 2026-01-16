#!/usr/bin/env python3
"""逐步檢查每個條件"""
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
print("逐步檢查每個條件")
print("=" * 80)

# Step 1: 只看 12 月 + V1
print("\n1. 12月 + V1 (不含排除):")
cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ = 'moNumber'
        GROUP BY PROC_INST_ID_
    )
    SELECT COUNT(*)
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
""")
print(f"   筆數: {cursor.fetchone()[0]:,}")

# Step 2: 檢查 region = CNE 的任務
print("\n2. 12月 + region = CNE:")
cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ = 'region'
        GROUP BY PROC_INST_ID_
    )
    SELECT COUNT(*)
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
    LEFT JOIN varinst_pivoted v ON t.ProcessInstanceId = v.PROC_INST_ID_
    WHERE t.TaskCreateDate >= '2025-12-01' 
      AND t.TaskCreateDate < '2026-01-01'
      AND v.region = 'CNE'
""")
print(f"   筆數: {cursor.fetchone()[0]:,}")

# Step 3: 檢查 Plant = WJ2
print("\n3. 12月 + Plant = WJ2:")
cursor.execute("""
    SELECT COUNT(*)
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
    WHERE t.TaskCreateDate >= '2025-12-01' 
      AND t.TaskCreateDate < '2026-01-01'
      AND t.Plant = 'WJ2'
""")
print(f"   筆數: {cursor.fetchone()[0]:,}")

# Step 4: 檢查 Factory = NBU
print("\n4. 12月 + Factory = NBU:")
cursor.execute("""
    SELECT COUNT(*)
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
    WHERE t.TaskCreateDate >= '2025-12-01' 
      AND t.TaskCreateDate < '2026-01-01'
      AND t.Factory = 'NBU'
""")
print(f"   筆數: {cursor.fetchone()[0]:,}")

# Step 5: 檢查 Line = E5
print("\n5. 12月 + Line = E5:")
cursor.execute("""
    SELECT COUNT(*)
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
    WHERE t.TaskCreateDate >= '2025-12-01' 
      AND t.TaskCreateDate < '2026-01-01'
      AND t.Line = 'E5'
""")
print(f"   筆數: {cursor.fetchone()[0]:,}")

# Step 6: 檢查 Line 欄位的值分布
print("\n6. 12月 Line 欄位值分布 (前20):")
cursor.execute("""
    SELECT TOP 20 Line, COUNT(*) as cnt
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
    WHERE t.TaskCreateDate >= '2025-12-01' 
      AND t.TaskCreateDate < '2026-01-01'
      AND Line IS NOT NULL
    GROUP BY Line
    ORDER BY cnt DESC
""")
for row in cursor.fetchall():
    print(f"   {row[0]}: {row[1]:,}")

# Step 7: 檢查 varinst.lineName 的值分布
print("\n7. varinst.lineName 值分布 (前20):")
cursor.execute("""
    SELECT TOP 20 TEXT_, COUNT(*) as cnt
    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
    WHERE NAME_ = 'lineName'
    GROUP BY TEXT_
    ORDER BY cnt DESC
""")
for row in cursor.fetchall():
    print(f"   {row[0]}: {row[1]:,}")

# Step 8: 組合條件 - V1 + WJ2 + NBU
print("\n8. 12月 + V1 + WJ2 + NBU:")
cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ = 'moNumber'
        GROUP BY PROC_INST_ID_
    )
    SELECT COUNT(*)
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
""")
print(f"   筆數: {cursor.fetchone()[0]:,}")

# Step 9: 檢查 V1 + WJ2 + NBU 的 Line 分布
print("\n9. V1 + WJ2 + NBU 的 Line 分布:")
cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ = 'moNumber'
        GROUP BY PROC_INST_ID_
    )
    SELECT TOP 20 t.Line, COUNT(*) as cnt
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
    GROUP BY t.Line
    ORDER BY cnt DESC
""")
for row in cursor.fetchall():
    print(f"   {row[0]}: {row[1]:,}")

conn.close()
