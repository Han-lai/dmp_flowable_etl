#!/usr/bin/env python3
"""檢查 CNS/CNE/DET 欄位來源"""
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
print("CNS/CNE/DET 欄位分析")
print("=" * 80)

print("\n1. Plant 欄位分布:")
cursor.execute("""
    SELECT Plant, COUNT(*) as cnt
    FROM APP_SRV_COMMON.dbo.FlowableTaskStats
    WHERE Plant IS NOT NULL
    GROUP BY Plant
    ORDER BY cnt DESC
""")
for row in cursor.fetchall():
    print(f"   {row[0]}: {row[1]:,}")

print("\n2. 檢查 NPE 是否在 BUSINESS_KEY_ 中:")
cursor.execute("""
    SELECT TOP 10 BUSINESS_KEY_
    FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST
    WHERE BUSINESS_KEY_ LIKE '%NPE%'
""")
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"   {row[0][:100]}...")
else:
    print("   沒有找到包含 NPE 的 BUSINESS_KEY_")

print("\n3. 檢查 varinst 中是否有 region/plant/factory 變數:")
cursor.execute("""
    SELECT NAME_, COUNT(*) as cnt
    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
    WHERE NAME_ IN ('region', 'plant', 'factory', 'Plant', 'Factory', 'Region')
    GROUP BY NAME_
    ORDER BY cnt DESC
""")
for row in cursor.fetchall():
    print(f"   {row[0]}: {row[1]:,}")

print("\n4. varinst 中 plant 變數的值分布:")
cursor.execute("""
    SELECT TEXT_, COUNT(*) as cnt
    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
    WHERE NAME_ = 'plant'
    GROUP BY TEXT_
    ORDER BY cnt DESC
""")
for row in cursor.fetchall():
    print(f"   {row[0]}: {row[1]:,}")

print("\n5. varinst 中 factory 變數的值分布:")
cursor.execute("""
    SELECT TOP 20 TEXT_, COUNT(*) as cnt
    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
    WHERE NAME_ = 'factory'
    GROUP BY TEXT_
    ORDER BY cnt DESC
""")
for row in cursor.fetchall():
    print(f"   {row[0]}: {row[1]:,}")

conn.close()
