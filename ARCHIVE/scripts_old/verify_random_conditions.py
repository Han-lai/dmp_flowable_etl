#!/usr/bin/env python3
"""
隨機條件驗證：ClickHouse vs MSSQL
"""
import pymssql
import clickhouse_connect
import random

print("=" * 100)
print("隨機條件驗證：ClickHouse vs MSSQL")
print("=" * 100)

# ClickHouse 連線
ch = clickhouse_connect.get_client(
    host='10.136.218.207',
    port=8121,
    username='default',
    password='default'
)

# 取得有資料的 date/plant/line 組合
result = ch.query("""
SELECT DISTINCT task_create_date, plant, line, count(*) as cnt
FROM silver.task_detail_wide FINAL
WHERE plant IS NOT NULL AND line IS NOT NULL
  AND task_create_date >= '2025-12-01'
  AND task_bypass = 'N'
GROUP BY task_create_date, plant, line
HAVING cnt >= 5 AND cnt <= 50
ORDER BY rand()
LIMIT 5
""")

print(f"\n隨機選取 5 組條件進行驗證：")
for row in result.result_rows:
    print(f"  date={row[0]}, plant={row[1]}, line={row[2]}, 預估筆數={row[3]}")

# MSSQL 連線
mssql_conn = pymssql.connect(
    server='twtpesqldv2.delta.corp',
    port='1433',
    user='DMP_APP_SRV',
    password='APP@DB#01',
    database='APP_SRV_BPM'
)
mssql_cursor = mssql_conn.cursor()

# 驗證每組條件
all_passed = True
for row in result.result_rows:
    date_val = str(row[0])
    plant_val = row[1]
    line_val = row[2]
    
    print(f"\n{'=' * 80}")
    print(f"驗證: date={date_val}, plant={plant_val}, line={line_val}, bypass=N")
    print("=" * 80)
    
    # MSSQL 查詢
    mssql_cursor.execute(f"""
    SELECT * FROM (
    SELECT
        hti.ID_ AS taskId,
        CASE
            WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
            WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
            ELSE 'TODO'
        END AS taskStatus,
        CASE WHEN var_bypass.LONG_ = 1 THEN 'Y' ELSE 'N' END AS taskBypass,
        var_plant.TEXT_ AS plant,
        var_lineName.TEXT_ AS line
    FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
    INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_bypass ON hti.ID_ = var_bypass.TASK_ID_ AND var_bypass.NAME_ = 'autoComplete'
    WHERE CONVERT(DATE, hti.START_TIME_) = '{date_val}'
    ) AS t
    WHERE taskBypass='N' AND plant='{plant_val}' AND line='{line_val}'
    ORDER BY taskId
    """)
    mssql_rows = mssql_cursor.fetchall()
    mssql_task_ids = set(row[0] for row in mssql_rows)
    mssql_status = {}
    for r in mssql_rows:
        mssql_status[r[1]] = mssql_status.get(r[1], 0) + 1
    
    # ClickHouse 查詢
    ch_result = ch.query(f"""
    SELECT task_id, task_status, task_bypass, plant, line
    FROM silver.task_detail_wide FINAL
    WHERE task_create_date = '{date_val}'
      AND task_bypass = 'N'
      AND plant = '{plant_val}'
      AND line = '{line_val}'
    ORDER BY task_id
    """)
    ch_task_ids = set(row[0] for row in ch_result.result_rows)
    ch_status = {}
    for r in ch_result.result_rows:
        ch_status[r[1]] = ch_status.get(r[1], 0) + 1
    
    # 建立明細對照 dict
    mssql_dict = {row[0]: {'status': row[1], 'bypass': row[2], 'plant': row[3], 'line': row[4]} for row in mssql_rows}
    ch_dict = {row[0]: {'status': row[1], 'bypass': row[2], 'plant': row[3], 'line': row[4]} for row in ch_result.result_rows}
    
    # 比對
    print(f"  MSSQL:      {len(mssql_rows)} 筆")
    print(f"  ClickHouse: {len(ch_result.result_rows)} 筆")
    
    only_mssql = mssql_task_ids - ch_task_ids
    only_ch = ch_task_ids - mssql_task_ids
    common_ids = mssql_task_ids & ch_task_ids
    
    # 明細比對
    detail_mismatch = []
    for tid in common_ids:
        m = mssql_dict[tid]
        c = ch_dict[tid]
        if m['status'] != c['status'] or m['bypass'] != c['bypass']:
            detail_mismatch.append({
                'task_id': tid,
                'mssql': m,
                'ch': c
            })
    
    if len(mssql_rows) == len(ch_result.result_rows) and not only_mssql and not only_ch and not detail_mismatch:
        print(f"  ✅ 通過（筆數 + 明細完全一致）")
    else:
        print(f"  ❌ 失敗")
        if only_mssql:
            print(f"     只在 MSSQL: {len(only_mssql)} 筆")
        if only_ch:
            print(f"     只在 ClickHouse: {len(only_ch)} 筆")
        if detail_mismatch:
            print(f"     明細不一致: {len(detail_mismatch)} 筆")
            for d in detail_mismatch[:3]:
                print(f"       {d['task_id']}: MSSQL={d['mssql']}, CH={d['ch']}")
        all_passed = False
    
    # 狀態分布
    print(f"  狀態分布:")
    all_statuses = set(mssql_status.keys()) | set(ch_status.keys())
    for s in sorted(all_statuses):
        m = mssql_status.get(s, 0)
        c = ch_status.get(s, 0)
        match = "✓" if m == c else "✗"
        print(f"    {s}: MSSQL={m}, CH={c} {match}")
    
    # 顯示明細對照（前 5 筆）
    print(f"  明細對照（前 5 筆）:")
    print(f"    {'task_id':<38} {'MSSQL_status':<12} {'CH_status':<12} {'match'}")
    print(f"    {'-'*75}")
    for tid in sorted(common_ids)[:5]:
        m_status = mssql_dict[tid]['status']
        c_status = ch_dict[tid]['status']
        match = "✓" if m_status == c_status else "✗"
        print(f"    {tid:<38} {m_status:<12} {c_status:<12} {match}")

mssql_conn.close()

print("\n" + "=" * 100)
if all_passed:
    print("✅ 全部驗證通過！")
else:
    print("⚠️ 部分驗證失敗")
print("=" * 100)
