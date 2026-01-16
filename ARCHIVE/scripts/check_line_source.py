#!/usr/bin/env python3
"""
檢查 V1 + CNE + WJ2 + NBU 的任務，比較 task.Line vs varinst.lineName
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

print("=" * 100)
print("V1 + CNE + WJ2 + NBU 的任務 Line 來源比較")
print("=" * 100)

cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region,
            MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS lineName
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('moNumber', 'region', 'lineName')
        GROUP BY PROC_INST_ID_
    )
    SELECT 
        t.TaskId,
        t.ProcessInstanceId,
        t.TaskStatus,
        t.Line as task_line,
        v.lineName as varinst_lineName
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
""")

rows = cursor.fetchall()
print(f"\n共 {len(rows)} 筆任務")
print(f"\n{'TaskStatus':<10} {'task.Line':<12} {'varinst.lineName':<20}")
print("-" * 50)
for row in rows:
    task_line = str(row[3]) if row[3] else 'NULL'
    varinst_line = str(row[4]) if row[4] else 'NULL'
    print(f"{row[2]:<10} {task_line:<12} {varinst_line:<20}")

# 統計 varinst.lineName 分布
print("\n" + "=" * 100)
print("varinst.lineName 分布統計")
print("=" * 100)

cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region,
            MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS lineName
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('moNumber', 'region', 'lineName')
        GROUP BY PROC_INST_ID_
    )
    SELECT 
        COALESCE(v.lineName, 'NULL') as lineName,
        COUNT(*) as cnt
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
    GROUP BY v.lineName
    ORDER BY cnt DESC
""")

print(f"\n{'lineName':<20} {'筆數':>10}")
print("-" * 35)
for row in cursor.fetchall():
    print(f"{row[0]:<20} {row[1]:>10}")

# 如果用 varinst.lineName = 'E5' 會得到什麼結果
print("\n" + "=" * 100)
print("使用 varinst.lineName = 'E5' 的結果")
print("=" * 100)

cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region,
            MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS lineName
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('moNumber', 'region', 'lineName')
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
      AND v.region = 'CNE'
      AND t.Plant = 'WJ2'
      AND t.Factory = 'NBU'
      AND v.lineName = 'E5'
""")

row = cursor.fetchone()
print(f"\n使用 varinst.lineName = 'E5' 結果:")
print(f"  Total: {row[0]}")
print(f"  TODO:  {row[1]}")
print(f"  DOING: {row[2]}")
print(f"  DONE:  {row[3]}")

print(f"\n預期結果:")
print(f"  Total: 14")
print(f"  TODO:  11")
print(f"  DOING: 2")
print(f"  DONE:  1")

conn.close()
