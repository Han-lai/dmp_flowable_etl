#!/usr/bin/env python3
"""
篩選邏輯依賴順序驗證
順序：V1 -> region -> WJ2 -> NBU -> E5
"""
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
print("篩選邏輯依賴順序驗證")
print("順序：V1 -> region -> WJ2 -> NBU -> E5")
print("=" * 80)

# ============================================
# Step 1: V1 母集合
# ============================================
print("\n" + "=" * 80)
print("Step 1: V1 母集合（12月）")
print("=" * 80)

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
        COUNT(*) as task_count,
        COUNT(DISTINCT t.ProcessInstanceId) as proc_count
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
row = cursor.fetchone()
print(f"V1 母集合: {row[0]:,} 任務 / {row[1]:,} 流程實例")

# ============================================
# Step 2: 在 V1 母集合上展開 region
# ============================================
print("\n" + "=" * 80)
print("Step 2: 在 V1 母集合上展開 region")
print("=" * 80)

cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('moNumber', 'region')
        GROUP BY PROC_INST_ID_
    ),
    v1_base AS (
        SELECT 
            t.TaskId,
            t.ProcessInstanceId,
            t.TaskStatus,
            t.Plant,
            t.Factory,
            t.Line,
            v.region
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
    )
    SELECT 
        COALESCE(region, 'NULL') as region,
        COUNT(*) as task_count,
        COUNT(DISTINCT ProcessInstanceId) as proc_count
    FROM v1_base
    GROUP BY region
    ORDER BY task_count DESC
""")
print("\nV1 母集合中的 region 分布:")
print(f"{'region':<15} {'任務數':>10} {'流程數':>10}")
print("-" * 40)
for row in cursor.fetchall():
    print(f"{row[0]:<15} {row[1]:>10,} {row[2]:>10,}")

# ============================================
# Step 3: V1 + CNE 後展開 WJ2
# ============================================
print("\n" + "=" * 80)
print("Step 3: V1 + CNE 後展開 Plant (WJ2)")
print("=" * 80)

cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('moNumber', 'region')
        GROUP BY PROC_INST_ID_
    ),
    v1_cne AS (
        SELECT 
            t.TaskId,
            t.ProcessInstanceId,
            t.TaskStatus,
            t.Plant,
            t.Factory,
            t.Line
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
          AND v.region = 'CNE'
    )
    SELECT 
        COALESCE(Plant, 'NULL') as plant,
        COUNT(*) as task_count,
        COUNT(DISTINCT ProcessInstanceId) as proc_count
    FROM v1_cne
    GROUP BY Plant
    ORDER BY task_count DESC
""")
print("\nV1 + CNE 中的 Plant 分布:")
print(f"{'Plant':<15} {'任務數':>10} {'流程數':>10}")
print("-" * 40)
for row in cursor.fetchall():
    print(f"{row[0]:<15} {row[1]:>10,} {row[2]:>10,}")

# ============================================
# Step 4: V1 + CNE + WJ2 後展開 NBU
# ============================================
print("\n" + "=" * 80)
print("Step 4: V1 + CNE + WJ2 後展開 Factory (NBU)")
print("=" * 80)

cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('moNumber', 'region')
        GROUP BY PROC_INST_ID_
    ),
    v1_cne_wj2 AS (
        SELECT 
            t.TaskId,
            t.ProcessInstanceId,
            t.TaskStatus,
            t.Plant,
            t.Factory,
            t.Line
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
          AND v.region = 'CNE'
          AND t.Plant = 'WJ2'
    )
    SELECT 
        COALESCE(Factory, 'NULL') as factory,
        COUNT(*) as task_count,
        COUNT(DISTINCT ProcessInstanceId) as proc_count
    FROM v1_cne_wj2
    GROUP BY Factory
    ORDER BY task_count DESC
""")
print("\nV1 + CNE + WJ2 中的 Factory 分布:")
print(f"{'Factory':<15} {'任務數':>10} {'流程數':>10}")
print("-" * 40)
for row in cursor.fetchall():
    print(f"{row[0]:<15} {row[1]:>10,} {row[2]:>10,}")

# ============================================
# Step 5: V1 + CNE + WJ2 + NBU 後展開 E5
# ============================================
print("\n" + "=" * 80)
print("Step 5: V1 + CNE + WJ2 + NBU 後展開 Line (E5)")
print("=" * 80)

cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('moNumber', 'region')
        GROUP BY PROC_INST_ID_
    ),
    v1_cne_wj2_nbu AS (
        SELECT 
            t.TaskId,
            t.ProcessInstanceId,
            t.TaskStatus,
            t.Plant,
            t.Factory,
            t.Line
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
          AND v.region = 'CNE'
          AND t.Plant = 'WJ2'
          AND t.Factory = 'NBU'
    )
    SELECT 
        COALESCE(Line, 'NULL') as line,
        COUNT(*) as task_count,
        COUNT(DISTINCT ProcessInstanceId) as proc_count
    FROM v1_cne_wj2_nbu
    GROUP BY Line
    ORDER BY task_count DESC
""")
print("\nV1 + CNE + WJ2 + NBU 中的 Line 分布:")
print(f"{'Line':<15} {'任務數':>10} {'流程數':>10}")
print("-" * 40)
for row in cursor.fetchall():
    print(f"{row[0]:<15} {row[1]:>10,} {row[2]:>10,}")

# ============================================
# Step 6: 最終結果 V1 + CNE + WJ2 + NBU + E5
# ============================================
print("\n" + "=" * 80)
print("Step 6: 最終結果 V1 + CNE + WJ2 + NBU + E5")
print("=" * 80)

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
        SUM(CASE WHEN LOWER(t.TaskStatus) = 'done' THEN 1 ELSE 0 END) as done,
        COUNT(DISTINCT t.ProcessInstanceId) as proc_count
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
      AND v.region = 'CNE'
      AND t.Plant = 'WJ2'
      AND t.Factory = 'NBU'
      AND t.Line = 'E5'
""")
row = cursor.fetchone()
print(f"\n實際結果:")
print(f"  Total: {row[0]}")
print(f"  TODO:  {row[1]}")
print(f"  DOING: {row[2]}")
print(f"  DONE:  {row[3]}")
print(f"  流程數: {row[4]}")

print(f"\n預期結果:")
print(f"  Total: 14")
print(f"  TODO:  11")
print(f"  DOING: 2")
print(f"  DONE:  1")

print("\n" + "=" * 80)
conn.close()
