#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
檢查 NPE 資料來源
"""

import clickhouse_connect

client = clickhouse_connect.get_client(
    host='REDACTED_IP',
    port=8121,
    username='default',
    password='default'
)

print("=" * 80)
print("檢查 NPE 資料來源")
print("=" * 80)
print()

# 1. 檢查源表中的 NPE 資料
print("步驟 1: 檢查 bronze.bpm_act_hi_varinst 中的 NPE 資料")
print("-" * 80)

result = client.query('''
SELECT 
    COUNT(*) as total_rows,
    COUNT(CASE WHEN NAME_ LIKE '%NPE%' THEN 1 END) as npe_count
FROM bronze.bpm_act_hi_varinst
''')

total, npe = result.result_rows[0]
print(f"總行數: {total}")
print(f"NPE 行數: {npe}")
print()

if npe > 0:
    print("✅ 源表中有 NPE 資料")
    
    # 查詢 NPE 變數名稱範例
    result2 = client.query('''
    SELECT DISTINCT NAME_
    FROM bronze.bpm_act_hi_varinst
    WHERE NAME_ LIKE '%NPE%'
    LIMIT 5
    ''')
    
    print("\n  NPE 變數名稱範例:")
    for row in result2.result_rows:
        print(f"    • {row[0]}")
else:
    print("❌ 源表中沒有 NPE 資料")

print()
print("=" * 80)
print("步驟 2: 檢查 mv_varinst_pivoted 的定義")
print("-" * 80)

result = client.query('SHOW CREATE TABLE silver.mv_varinst_pivoted')
ddl = result.result_rows[0][0]

# 檢查 DDL 中是否有 NPE 相關邏輯
if "NAME_" in ddl or "varinst_name" in ddl:
    print("✅ MView 中有 varinst_name 欄位")
else:
    print("❌ MView 中沒有 varinst_name 欄位")

# 顯示 DDL 的前 2000 字
print("\nMView DDL (前 2000 字):")
print("-" * 80)
print(ddl[:2000])
print("...")

print()
print("=" * 80)
print("步驟 3: 檢查 mv_varinst_pivoted 中的 NPE 資料")
print("-" * 80)

result = client.query('''
SELECT 
    COUNT(*) as total_rows,
    COUNT(CASE WHEN varinst_name LIKE '%NPE%' THEN 1 END) as npe_count
FROM silver.mv_varinst_pivoted
''')

total, npe = result.result_rows[0]
print(f"總行數: {total}")
print(f"NPE 行數: {npe}")

if npe > 0:
    print("✅ MView 中有 NPE 資料")
else:
    print("❌ MView 中沒有 NPE 資料")

print()
print("=" * 80)
print("步驟 4: 檢查 mv_fact_task_vx_attribution 中的 NPE 邏輯")
print("-" * 80)

result = client.query('''
SELECT 
    COUNT(*) as total_rows,
    COUNT(CASE WHEN vx_subtype = 'V1_NPE' THEN 1 END) as v1_npe_count,
    COUNT(CASE WHEN vx_subtype = 'V1_MFG' THEN 1 END) as v1_mfg_count
FROM silver.mv_fact_task_vx_attribution
''')

total, npe, mfg = result.result_rows[0]
print(f"總行數: {total}")
print(f"V1_NPE: {npe}")
print(f"V1_MFG: {mfg}")

if npe == 0:
    print("\n❌ 問題: V1_NPE 完全缺失")
    print("   根本原因: mv_varinst_pivoted 中沒有 NPE 資料")
else:
    print("\n✅ NPE 邏輯正常")

print()
print("=" * 80)
