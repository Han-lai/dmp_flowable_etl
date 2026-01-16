#!/usr/bin/env python3
"""
ACT_HI_VARINST 變數寬表化（Pivot）檢查
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

# 要檢查的變數清單
VARIABLES = [
    'plant', 'sapPlant', 'sapProductGroup', 'factory', 'lineName',
    'modelName', 'moNumber', 'scheduleNumber', 'productionArea',
    'deliveryArea', 'pallet', 'transferNo', 'qBlockEventId',
    'defectSn', 'time', 'initiator', '_PROCESS_NODE_INFO', 'region'
]

print("=" * 80)
print("ACT_HI_VARINST 變數寬表化（Pivot）檢查")
print("=" * 80)

# ============================================
# 檢查 1: 每個變數的值是否都在 TEXT_ 欄位
# ============================================
print("\n" + "=" * 80)
print("檢查 1: 每個變數的值欄位分布")
print("=" * 80)

print(f"\n{'變數名稱':<25} {'TEXT_有值':>10} {'LONG_有值':>10} {'DOUBLE_有值':>12} {'總筆數':>10}")
print("-" * 80)

for var in VARIABLES:
    cursor.execute(f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN TEXT_ IS NOT NULL AND TEXT_ != '' THEN 1 ELSE 0 END) as text_cnt,
            SUM(CASE WHEN LONG_ IS NOT NULL THEN 1 ELSE 0 END) as long_cnt,
            SUM(CASE WHEN DOUBLE_ IS NOT NULL THEN 1 ELSE 0 END) as double_cnt
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ = '{var}'
    """)
    row = cursor.fetchone()
    if row[0] > 0:
        print(f"{var:<25} {row[1]:>10,} {row[2]:>10,} {row[3]:>12,} {row[0]:>10,}")

# ============================================
# 檢查 2: 同一個 PROC_INST_ID_ + NAME_ 是否有多筆
# ============================================
print("\n" + "=" * 80)
print("檢查 2: 同一個 PROC_INST_ID_ + NAME_ 是否有多筆")
print("=" * 80)

print(f"\n{'變數名稱':<25} {'不重複流程數':>12} {'總筆數':>10} {'有重複':>8}")
print("-" * 60)

for var in VARIABLES:
    cursor.execute(f"""
        SELECT 
            COUNT(DISTINCT PROC_INST_ID_) as distinct_proc,
            COUNT(*) as total
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ = '{var}'
    """)
    row = cursor.fetchone()
    if row[1] > 0:
        has_dup = "是" if row[1] > row[0] else "否"
        print(f"{var:<25} {row[0]:>12,} {row[1]:>10,} {has_dup:>8}")

# 檢查有重複的變數的詳細情況
print("\n檢查有重複的變數詳情:")
for var in VARIABLES:
    cursor.execute(f"""
        SELECT PROC_INST_ID_, COUNT(*) as cnt
        FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
        WHERE NAME_ = '{var}'
        GROUP BY PROC_INST_ID_
        HAVING COUNT(*) > 1
    """)
    rows = cursor.fetchall()
    if rows:
        print(f"\n  {var}: {len(rows)} 個流程有重複")
        # 顯示前 3 個範例
        for row in rows[:3]:
            cursor.execute(f"""
                SELECT TEXT_, CREATE_TIME_
                FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
                WHERE PROC_INST_ID_ = '{row[0]}' AND NAME_ = '{var}'
                ORDER BY CREATE_TIME_
            """)
            vals = cursor.fetchall()
            print(f"    PROC_INST_ID_={row[0][:20]}... 有 {row[1]} 筆:")
            for v in vals:
                print(f"      TEXT_={v[0]}, CREATE_TIME_={v[1]}")

# ============================================
# 檢查 3: 流程實例總數
# ============================================
print("\n" + "=" * 80)
print("檢查 3: 流程實例總數")
print("=" * 80)

cursor.execute("""
    SELECT COUNT(DISTINCT PROC_INST_ID_) 
    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
""")
print(f"\nVARINST 中不重複的 PROC_INST_ID_: {cursor.fetchone()[0]:,}")

cursor.execute("""
    SELECT COUNT(*) 
    FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST
""")
print(f"PROCINST 中的流程實例數: {cursor.fetchone()[0]:,}")

# ============================================
# Pivot SQL 範例
# ============================================
print("\n" + "=" * 80)
print("Pivot SQL 範例")
print("=" * 80)

pivot_sql = """
-- ACT_HI_VARINST Pivot 寬表 SQL
-- 取值規則：同 PROC_INST_ID_ + NAME_ 多筆時，取 MAX(TEXT_)
SELECT 
    PROC_INST_ID_,
    MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS plant,
    MAX(CASE WHEN NAME_ = 'sapPlant' THEN TEXT_ END) AS sapPlant,
    MAX(CASE WHEN NAME_ = 'sapProductGroup' THEN TEXT_ END) AS sapProductGroup,
    MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS factory,
    MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS lineName,
    MAX(CASE WHEN NAME_ = 'modelName' THEN TEXT_ END) AS modelName,
    MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS moNumber,
    MAX(CASE WHEN NAME_ = 'scheduleNumber' THEN TEXT_ END) AS scheduleNumber,
    MAX(CASE WHEN NAME_ = 'productionArea' THEN TEXT_ END) AS productionArea,
    MAX(CASE WHEN NAME_ = 'deliveryArea' THEN TEXT_ END) AS deliveryArea,
    MAX(CASE WHEN NAME_ = 'pallet' THEN TEXT_ END) AS pallet,
    MAX(CASE WHEN NAME_ = 'transferNo' THEN TEXT_ END) AS transferNo,
    MAX(CASE WHEN NAME_ = 'qBlockEventId' THEN TEXT_ END) AS qBlockEventId,
    MAX(CASE WHEN NAME_ = 'defectSn' THEN TEXT_ END) AS defectSn,
    MAX(CASE WHEN NAME_ = 'time' THEN TEXT_ END) AS time,
    MAX(CASE WHEN NAME_ = 'initiator' THEN TEXT_ END) AS initiator,
    MAX(CASE WHEN NAME_ = '_PROCESS_NODE_INFO' THEN TEXT_ END) AS process_node_info,
    MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region
FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
WHERE NAME_ IN (
    'plant', 'sapPlant', 'sapProductGroup', 'factory', 'lineName',
    'modelName', 'moNumber', 'scheduleNumber', 'productionArea',
    'deliveryArea', 'pallet', 'transferNo', 'qBlockEventId',
    'defectSn', 'time', 'initiator', '_PROCESS_NODE_INFO', 'region'
)
GROUP BY PROC_INST_ID_
"""
print(pivot_sql)

conn.close()
