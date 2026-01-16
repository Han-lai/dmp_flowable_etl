#!/usr/bin/env python3
"""
任務狀態統計可行性驗證
條件：V1 / CNE / WJ2 / NBU / E5 / 2025-12
預期：Total=14, TODO=11, DOING=2, DONE=1
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
print("任務狀態統計可行性驗證")
print("=" * 80)

print("\n" + "=" * 80)
print("一、Schema / Mapping Check")
print("=" * 80)

print("\n### 1. 任務主體欄位確認")
print("- 任務唯一識別鍵: TaskId (FlowableTaskStats)")
print("- 任務狀態欄位: TaskStatus (Todo/Doing/Done)")
print("- 任務時間欄位: TaskCreateDate, TaskEndDate")

print("\n### 2. 維度來源檢查")

# 檢查 varinst 中有哪些維度欄位
print("\n檢查 varinst 中的維度變數:")
cursor.execute("""
    SELECT NAME_, COUNT(*) as cnt
    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
    WHERE NAME_ IN ('region', 'plant', 'factory', 'lineName', 'moNumber')
    GROUP BY NAME_
    ORDER BY cnt DESC
""")
for row in cursor.fetchall():
    print(f"   {row[0]}: {row[1]:,}")

# 檢查 FlowableTaskStats 中的維度欄位
print("\n檢查 FlowableTaskStats 中的維度欄位:")
cursor.execute("""
    SELECT TOP 5 Plant, Factory, Line
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats
    WHERE Plant IS NOT NULL AND Factory IS NOT NULL AND Line IS NOT NULL
""")
for row in cursor.fetchall():
    print(f"   Plant={row[0]} | Factory={row[1]} | Line={row[2]}")

# 檢查 region 欄位的值分布
print("\n檢查 varinst.region 的值分布:")
cursor.execute("""
    SELECT TEXT_, COUNT(*) as cnt
    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
    WHERE NAME_ = 'region'
    GROUP BY TEXT_
    ORDER BY cnt DESC
""")
for row in cursor.fetchall():
    print(f"   {row[0]}: {row[1]:,}")

print("\n" + "=" * 80)
print("二、維度來源對應表")
print("=" * 80)

print("""
| 維度           | 實際來源                                      |
|----------------|-----------------------------------------------|
| 流程團隊 (V1)  | TaskDefinitionKey 前兩字元 或 moNumber 開頭判斷 |
| 地區 (CNE)     | varinst.region                                |
| 製造廠區 (WJ2) | FlowableTaskStats.Plant 或 varinst.plant      |
| 製造產品廠 (NBU)| FlowableTaskStats.Factory 或 varinst.factory  |
| 線體 (E5)      | FlowableTaskStats.Line 或 varinst.lineName    |
""")

print("\n" + "=" * 80)
print("三、實際查詢驗證")
print("=" * 80)

# 使用 varinst 轉置取得維度
print("\n使用 varinst 轉置 + FlowableTaskStats 查詢:")
cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region,
            MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS var_plant,
            MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS var_factory,
            MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS var_lineName
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('moNumber', 'region', 'plant', 'factory', 'lineName')
        GROUP BY PROC_INST_ID_
    )
    SELECT 
        t.TaskId,
        t.TaskStatus,
        t.TaskDefinitionKey,
        t.TaskCreateDate,
        t.Plant,
        t.Factory,
        t.Line,
        v.region,
        v.var_plant,
        v.var_factory,
        v.var_lineName,
        v.moNumber
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
    LEFT JOIN varinst_pivoted v ON t.ProcessInstanceId = v.PROC_INST_ID_
    WHERE t.TaskCreateDate >= '2025-12-01' 
      AND t.TaskCreateDate < '2026-01-01'
      AND t.TaskBypass = 'N'
      AND t.TaskDefinitionKey NOT LIKE 'E%'
      AND t.TaskDefinitionKey NOT LIKE 'C%'
      -- V1 條件
      AND (
          t.TaskDefinitionKey LIKE 'V1%'
          OR v.moNumber LIKE '196%' OR v.moNumber LIKE '199%' OR v.moNumber LIKE '200%'
          OR v.moNumber LIKE '210%' OR v.moNumber LIKE '212%' OR v.moNumber LIKE '213%'
          OR v.moNumber LIKE '315%'
      )
      -- CNE 條件
      AND v.region = 'CNE'
      -- WJ2 條件
      AND (t.Plant = 'WJ2' OR v.var_plant = 'WJ2')
      -- NBU 條件
      AND (t.Factory = 'NBU' OR v.var_factory = 'NBU')
      -- E5 條件
      AND (t.Line = 'E5' OR v.var_lineName = 'E5')
""")
rows = cursor.fetchall()
print(f"\n查詢結果筆數: {len(rows)}")
for row in rows:
    print(f"   TaskId={row[0]} | Status={row[1]} | DefKey={row[2]} | Date={row[3]}")
    print(f"      Plant={row[4]} | Factory={row[5]} | Line={row[6]}")
    print(f"      region={row[7]} | var_plant={row[8]} | var_factory={row[9]} | var_lineName={row[10]}")

# 統計結果
print("\n統計結果:")
cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region,
            MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS var_plant,
            MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS var_factory,
            MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS var_lineName
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('moNumber', 'region', 'plant', 'factory', 'lineName')
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
      AND (t.Plant = 'WJ2' OR v.var_plant = 'WJ2')
      AND (t.Factory = 'NBU' OR v.var_factory = 'NBU')
      AND (t.Line = 'E5' OR v.var_lineName = 'E5')
""")
row = cursor.fetchone()
print(f"   Total: {row[0]}")
print(f"   TODO:  {row[1]}")
print(f"   DOING: {row[2]}")
print(f"   DONE:  {row[3]}")

print("\n預期結果:")
print("   Total: 14")
print("   TODO:  11")
print("   DOING: 2")
print("   DONE:  1")

conn.close()
