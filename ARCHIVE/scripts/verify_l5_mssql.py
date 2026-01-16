#!/usr/bin/env python3
"""
在 MSSQL 上驗證 L5 任務執行完成率計算邏輯
使用相同的邏輯：varinst.moNumber 開頭判斷
"""
import pymssql

# MSSQL 連線設定
MSSQL_CONFIG = {
    'server': 'twtpesqldv2.delta.corp',
    'port': '1433',
    'user': 'DMP_APP_SRV',
    'password': 'APP@DB#01',
    'database': 'APP_SRV_BPM'
}

def get_conn():
    return pymssql.connect(**MSSQL_CONFIG)

print("=" * 80)
print("L5 任務執行完成率 - MSSQL 原始資料驗證")
print("=" * 80)

conn = get_conn()
cursor = conn.cursor()

# 1. 總任務數（從 FlowableTaskStats）
print("\n1. 總任務數:")
cursor.execute("""
    SELECT COUNT(*) 
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats 
    WHERE TaskId IS NOT NULL AND TaskId != ''
""")
total = cursor.fetchone()[0]
print(f"   總任務數: {total:,}")

# 2. 排除後的有效任務數
print("\n2. 排除原因分布:")
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
        CASE 
            WHEN t.TaskBypass != 'N' THEN 'bypass'
            WHEN t.TaskDefinitionKey LIKE 'E%' THEN 'E_prefix'
            WHEN t.TaskDefinitionKey LIKE 'C%' THEN 'C_prefix'
            WHEN COALESCE(v.moNumber, t.MoNumber) LIKE 'Q%' THEN 'Q_order'
            WHEN COALESCE(v.moNumber, t.MoNumber) LIKE 'R%' THEN 'R_order'
            ELSE 'valid'
        END AS exclude_reason,
        COUNT(*) as cnt
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
    LEFT JOIN varinst_pivoted v ON t.ProcessInstanceId = v.PROC_INST_ID_
    WHERE t.TaskId IS NOT NULL AND t.TaskId != ''
    GROUP BY 
        CASE 
            WHEN t.TaskBypass != 'N' THEN 'bypass'
            WHEN t.TaskDefinitionKey LIKE 'E%' THEN 'E_prefix'
            WHEN t.TaskDefinitionKey LIKE 'C%' THEN 'C_prefix'
            WHEN COALESCE(v.moNumber, t.MoNumber) LIKE 'Q%' THEN 'Q_order'
            WHEN COALESCE(v.moNumber, t.MoNumber) LIKE 'R%' THEN 'R_order'
            ELSE 'valid'
        END
    ORDER BY cnt DESC
""")
for row in cursor.fetchall():
    print(f"   {row[0]}: {row[1]:,}")

# 3. Vx 分布（排除後）
print("\n3. Vx 分布（排除後）:")
cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ = 'moNumber'
        GROUP BY PROC_INST_ID_
    ),
    task_with_vx AS (
        SELECT 
            t.TaskId,
            t.TaskStatus,
            t.TaskBypass,
            t.TaskDefinitionKey,
            t.TaskCreateDate,
            COALESCE(v.moNumber, t.MoNumber) AS mo_number,
            p.BUSINESS_KEY_,
            -- Vx 歸屬
            CASE 
                WHEN COALESCE(v.moNumber, t.MoNumber) LIKE '196%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '199%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '200%'
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '210%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '212%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '213%'
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '315%'
                THEN 'V1'
                ELSE COALESCE(SUBSTRING(t.TaskDefinitionKey, 1, 2), 'Unknown')
            END AS vx_type,
            -- 排除標記
            CASE 
                WHEN t.TaskBypass != 'N' THEN 1
                WHEN t.TaskDefinitionKey LIKE 'E%' OR t.TaskDefinitionKey LIKE 'C%' THEN 1
                WHEN COALESCE(v.moNumber, t.MoNumber) LIKE 'Q%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE 'R%' THEN 1
                ELSE 0
            END AS is_excluded
        FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_PROCINST p ON t.ProcessInstanceId = p.PROC_INST_ID_
        LEFT JOIN varinst_pivoted v ON t.ProcessInstanceId = v.PROC_INST_ID_
        WHERE t.TaskId IS NOT NULL AND t.TaskId != ''
    )
    SELECT vx_type, COUNT(*) as cnt
    FROM task_with_vx
    WHERE is_excluded = 0
    GROUP BY vx_type
    ORDER BY cnt DESC
""")
for row in cursor.fetchall():
    print(f"   {row[0]}: {row[1]:,}")

# 4. 2025-12 月份 L5 指標（V1 All）
print("\n4. 2025-12 月份 L5 指標（V1 All）:")
cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ = 'moNumber'
        GROUP BY PROC_INST_ID_
    ),
    task_with_vx AS (
        SELECT 
            t.TaskId,
            t.TaskStatus,
            t.TaskBypass,
            t.TaskDefinitionKey,
            t.TaskCreateDate,
            COALESCE(v.moNumber, t.MoNumber) AS mo_number,
            p.BUSINESS_KEY_,
            CASE 
                WHEN COALESCE(v.moNumber, t.MoNumber) LIKE '196%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '199%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '200%'
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '210%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '212%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '213%'
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '315%'
                THEN 'V1'
                ELSE COALESCE(SUBSTRING(t.TaskDefinitionKey, 1, 2), 'Unknown')
            END AS vx_type,
            CASE 
                WHEN t.TaskBypass != 'N' THEN 1
                WHEN t.TaskDefinitionKey LIKE 'E%' OR t.TaskDefinitionKey LIKE 'C%' THEN 1
                WHEN COALESCE(v.moNumber, t.MoNumber) LIKE 'Q%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE 'R%' THEN 1
                ELSE 0
            END AS is_excluded
        FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_PROCINST p ON t.ProcessInstanceId = p.PROC_INST_ID_
        LEFT JOIN varinst_pivoted v ON t.ProcessInstanceId = v.PROC_INST_ID_
        WHERE t.TaskId IS NOT NULL AND t.TaskId != ''
    )
    SELECT 
        COUNT(*) as total_task,
        SUM(CASE WHEN LOWER(TaskStatus) = 'todo' THEN 1 ELSE 0 END) as todo,
        SUM(CASE WHEN LOWER(TaskStatus) = 'doing' THEN 1 ELSE 0 END) as doing,
        SUM(CASE WHEN LOWER(TaskStatus) = 'done' THEN 1 ELSE 0 END) as done
    FROM task_with_vx
    WHERE TaskCreateDate >= '2025-12-01' 
      AND TaskCreateDate < '2026-01-01'
      AND is_excluded = 0
      AND vx_type = 'V1'
""")
row = cursor.fetchone()
total_task = row[0]
todo = row[1]
doing = row[2]
done = row[3]
print(f"   Total Task: {total_task:,}")
print(f"   Todo: {todo:,} ({todo*100/total_task:.2f}%)")
print(f"   Doing: {doing:,} ({doing*100/total_task:.2f}%)")
print(f"   Done: {done:,} ({done*100/total_task:.2f}%)")
print(f"   Doing + Done: {doing+done:,} ({(doing+done)*100/total_task:.2f}%)")

# 5. V1 子類型分布（V1_NPE vs V1_MFG）
print("\n5. 2025-12 月份 V1 NPE vs V1 MFG:")
cursor.execute("""
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ = 'moNumber'
        GROUP BY PROC_INST_ID_
    ),
    task_with_vx AS (
        SELECT 
            t.TaskId,
            t.TaskStatus,
            t.TaskBypass,
            t.TaskDefinitionKey,
            t.TaskCreateDate,
            COALESCE(v.moNumber, t.MoNumber) AS mo_number,
            p.BUSINESS_KEY_,
            CASE 
                WHEN COALESCE(v.moNumber, t.MoNumber) LIKE '196%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '199%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '200%'
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '210%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '212%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '213%'
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE '315%'
                THEN 'V1'
                ELSE COALESCE(SUBSTRING(t.TaskDefinitionKey, 1, 2), 'Unknown')
            END AS vx_type,
            -- V1 子類型
            CASE 
                WHEN (COALESCE(v.moNumber, t.MoNumber) LIKE '196%' 
                      OR COALESCE(v.moNumber, t.MoNumber) LIKE '199%' 
                      OR COALESCE(v.moNumber, t.MoNumber) LIKE '200%'
                      OR COALESCE(v.moNumber, t.MoNumber) LIKE '210%' 
                      OR COALESCE(v.moNumber, t.MoNumber) LIKE '212%' 
                      OR COALESCE(v.moNumber, t.MoNumber) LIKE '213%'
                      OR COALESCE(v.moNumber, t.MoNumber) LIKE '315%')
                     AND p.BUSINESS_KEY_ LIKE '%NPE%'
                THEN 'V1_NPE'
                WHEN (COALESCE(v.moNumber, t.MoNumber) LIKE '196%' 
                      OR COALESCE(v.moNumber, t.MoNumber) LIKE '199%' 
                      OR COALESCE(v.moNumber, t.MoNumber) LIKE '200%'
                      OR COALESCE(v.moNumber, t.MoNumber) LIKE '210%' 
                      OR COALESCE(v.moNumber, t.MoNumber) LIKE '212%' 
                      OR COALESCE(v.moNumber, t.MoNumber) LIKE '213%'
                      OR COALESCE(v.moNumber, t.MoNumber) LIKE '315%')
                THEN 'V1_MFG'
                ELSE NULL
            END AS vx_subtype,
            CASE 
                WHEN t.TaskBypass != 'N' THEN 1
                WHEN t.TaskDefinitionKey LIKE 'E%' OR t.TaskDefinitionKey LIKE 'C%' THEN 1
                WHEN COALESCE(v.moNumber, t.MoNumber) LIKE 'Q%' 
                     OR COALESCE(v.moNumber, t.MoNumber) LIKE 'R%' THEN 1
                ELSE 0
            END AS is_excluded
        FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_PROCINST p ON t.ProcessInstanceId = p.PROC_INST_ID_
        LEFT JOIN varinst_pivoted v ON t.ProcessInstanceId = v.PROC_INST_ID_
        WHERE t.TaskId IS NOT NULL AND t.TaskId != ''
    )
    SELECT 
        COALESCE(vx_subtype, 'NULL (非特殊規則)') as subtype,
        COUNT(*) as total_task,
        SUM(CASE WHEN LOWER(TaskStatus) = 'todo' THEN 1 ELSE 0 END) as todo,
        SUM(CASE WHEN LOWER(TaskStatus) = 'doing' THEN 1 ELSE 0 END) as doing,
        SUM(CASE WHEN LOWER(TaskStatus) = 'done' THEN 1 ELSE 0 END) as done
    FROM task_with_vx
    WHERE TaskCreateDate >= '2025-12-01' 
      AND TaskCreateDate < '2026-01-01'
      AND is_excluded = 0
      AND vx_type = 'V1'
    GROUP BY vx_subtype
    ORDER BY vx_subtype
""")
for row in cursor.fetchall():
    subtype = row[0]
    total = row[1]
    todo = row[2]
    doing = row[3]
    done = row[4]
    print(f"\n   {subtype}:")
    print(f"      Total: {total:,}")
    print(f"      Todo: {todo:,} | Doing: {doing:,} | Done: {done:,}")

print("\n" + "=" * 80)
conn.close()
