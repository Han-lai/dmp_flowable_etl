#!/usr/bin/env python3
"""
驗證 Pivot 前後筆數是否一致、是否倍增、NULL 比例
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
print("驗證 Pivot 前後筆數")
print("=" * 80)

# Pivot 後的筆數
cursor.execute("""
    WITH varinst_pivot AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS plant,
            MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS factory,
            MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS lineName,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('plant', 'factory', 'lineName', 'moNumber', 'region')
        GROUP BY PROC_INST_ID_
    )
    SELECT 
        COUNT(*) as pivot_rows,
        COUNT(DISTINCT PROC_INST_ID_) as distinct_proc
    FROM varinst_pivot
""")
row = cursor.fetchone()
print(f"\nPivot 後: {row[0]:,} 列 / {row[1]:,} 不重複流程")
print(f"是否倍增: {'否' if row[0] == row[1] else '是'}")

# NULL 比例
print("\n" + "=" * 80)
print("各欄位 NULL 比例")
print("=" * 80)

cursor.execute("""
    WITH varinst_pivot AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS plant,
            MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS factory,
            MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS lineName,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('plant', 'factory', 'lineName', 'moNumber', 'region')
        GROUP BY PROC_INST_ID_
    )
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN plant IS NULL THEN 1 ELSE 0 END) as plant_null,
        SUM(CASE WHEN factory IS NULL THEN 1 ELSE 0 END) as factory_null,
        SUM(CASE WHEN lineName IS NULL THEN 1 ELSE 0 END) as lineName_null,
        SUM(CASE WHEN moNumber IS NULL THEN 1 ELSE 0 END) as moNumber_null,
        SUM(CASE WHEN region IS NULL THEN 1 ELSE 0 END) as region_null
    FROM varinst_pivot
""")
row = cursor.fetchone()
total = row[0]
print(f"\n{'欄位':<15} {'NULL 數':>10} {'NULL %':>10}")
print("-" * 40)
print(f"{'plant':<15} {row[1]:>10,} {row[1]*100/total:>9.1f}%")
print(f"{'factory':<15} {row[2]:>10,} {row[2]*100/total:>9.1f}%")
print(f"{'lineName':<15} {row[3]:>10,} {row[3]*100/total:>9.1f}%")
print(f"{'moNumber':<15} {row[4]:>10,} {row[4]*100/total:>9.1f}%")
print(f"{'region':<15} {row[5]:>10,} {row[5]*100/total:>9.1f}%")

# JOIN 回主表驗證
print("\n" + "=" * 80)
print("JOIN 回 FlowableTaskStats 驗證")
print("=" * 80)

cursor.execute("""
    SELECT COUNT(*) FROM APP_SRV_COMMON.dbo.FlowableTaskStats
""")
task_count = cursor.fetchone()[0]
print(f"\nFlowableTaskStats 總筆數: {task_count:,}")

cursor.execute("""
    WITH varinst_pivot AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS plant,
            MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS factory,
            MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS lineName,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
            MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ IN ('plant', 'factory', 'lineName', 'moNumber', 'region')
        GROUP BY PROC_INST_ID_
    )
    SELECT 
        COUNT(*) as joined_rows,
        COUNT(DISTINCT t.TaskId) as distinct_tasks
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats t
    LEFT JOIN varinst_pivot v ON t.ProcessInstanceId = v.PROC_INST_ID_
""")
row = cursor.fetchone()
print(f"JOIN 後筆數: {row[0]:,}")
print(f"不重複 TaskId: {row[1]:,}")
print(f"是否倍增: {'否' if row[0] == task_count else '是'}")

conn.close()
