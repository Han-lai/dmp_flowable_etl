"""
比較三種環境的 17 個指標
- Benchmark: 參考環境 (flowable_analytics)
- View: 你的環境 View (silver.V_*)
- RMV: 你的環境 RMV (silver.RMV_*)
"""
import clickhouse_connect

my_client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')
ref_client = clickhouse_connect.get_client(host='REDACTED_IP', port=8124, username='ch_user', password='ch_strong_password_change_me')

print('=' * 120)
print('17 個指標 - 三種環境比較 (Benchmark / View / RMV)')
print('=' * 120)

# 定義指標查詢
# (指標名稱, Benchmark SQL, View SQL, RMV SQL, 說明)
METRICS = [
    # === 任務層指標 ===
    ("1. 在途任務總數",
     "SELECT count(*) FROM flowable_analytics.silver_enriched_taskinst WHERE task_state IN ('TODO', 'DOING')",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING')",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS IN ('TODO', 'DOING')",
     "任務層"),
    
    ("2. TODO 任務數",
     "SELECT count(*) FROM flowable_analytics.silver_enriched_taskinst WHERE task_state = 'TODO'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'TODO'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'TODO'",
     "任務層"),
    
    ("3. DOING 任務數",
     "SELECT count(*) FROM flowable_analytics.silver_enriched_taskinst WHERE task_state = 'DOING'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DOING'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DOING'",
     "任務層"),
    
    ("4. DONE 任務數",
     "SELECT count(*) FROM flowable_analytics.silver_enriched_taskinst WHERE task_state = 'DONE'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE'",
     "任務層"),
    
    ("5. DONE_AUTO 任務數",
     "SELECT count(*) FROM flowable_analytics.silver_enriched_taskinst WHERE task_state = 'DONE_AUTO'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE_AUTO'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'DONE_AUTO'",
     "任務層"),
    
    ("6. CANCELLED 任務數",
     "SELECT count(*) FROM flowable_analytics.silver_enriched_taskinst WHERE task_state = 'TERMINATED'",
     "SELECT count(*) FROM silver.V_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'CANCELLED'",
     "SELECT count(*) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TASK_STATUS = 'CANCELLED'",
     "任務層"),
    
    ("7. 自動完成率 (%)",
     "SELECT round(countIf(task_state = 'DONE_AUTO') * 100.0 / countIf(task_state IN ('DONE', 'DONE_AUTO')), 2) FROM flowable_analytics.silver_enriched_taskinst",
     "SELECT round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) FROM silver.V_HI_PROC_TASK_NODE",
     "SELECT round(countIf(TASK_STATUS = 'DONE_AUTO') * 100.0 / countIf(TASK_STATUS IN ('DONE', 'DONE_AUTO')), 2) FROM silver.RMV_HI_PROC_TASK_NODE",
     "任務層"),
    
    ("8. 平均任務處理時長 (秒)",
     "SELECT round(avg(processing_duration_seconds), 2) FROM flowable_analytics.silver_enriched_taskinst WHERE processing_duration_seconds IS NOT NULL",
     "SELECT round(avg(WORK_DURATION_SEC), 2) FROM silver.V_HI_PROC_TASK_NODE WHERE WORK_DURATION_SEC IS NOT NULL",
     "SELECT round(avg(WORK_DURATION_SEC), 2) FROM silver.RMV_HI_PROC_TASK_NODE WHERE WORK_DURATION_SEC IS NOT NULL",
     "任務層"),
    
    ("9. 平均任務總歷時 (秒)",
     "SELECT round(avg(total_duration_seconds), 2) FROM flowable_analytics.silver_enriched_taskinst WHERE total_duration_seconds IS NOT NULL",
     "SELECT round(avg(TOTAL_DURATION_SEC), 2) FROM silver.V_HI_PROC_TASK_NODE WHERE TOTAL_DURATION_SEC IS NOT NULL",
     "SELECT round(avg(TOTAL_DURATION_SEC), 2) FROM silver.RMV_HI_PROC_TASK_NODE WHERE TOTAL_DURATION_SEC IS NOT NULL",
     "任務層"),
    
    # === 流程層指標 ===
    ("10. 流程實例總數",
     "SELECT count(*) FROM flowable_analytics.silver_enriched_procinst",
     "SELECT count(*) FROM silver.V_HI_PROCINST_NODE",
     "SELECT count(*) FROM silver.RMV_HI_PROCINST_NODE",
     "流程層"),
    
    ("11. 在途流程數",
     "SELECT count(*) FROM flowable_analytics.silver_enriched_procinst WHERE proc_state = 'RUNNING'",
     "SELECT count(*) FROM silver.V_HI_PROCINST_NODE WHERE PROC_STATE = 'DOING'",
     "SELECT count(*) FROM silver.RMV_HI_PROCINST_NODE WHERE PROC_STATE = 'DOING'",
     "流程層"),
    
    ("12. 已完成流程數",
     "SELECT count(*) FROM flowable_analytics.silver_enriched_procinst WHERE proc_state = 'COMPLETED'",
     "SELECT count(*) FROM silver.V_HI_PROCINST_NODE WHERE PROC_STATE = 'DONE'",
     "SELECT count(*) FROM silver.RMV_HI_PROCINST_NODE WHERE PROC_STATE = 'DONE'",
     "流程層"),
    
    ("13. 終止流程數",
     "SELECT count(*) FROM flowable_analytics.silver_enriched_procinst WHERE proc_state = 'TERMINATED'",
     "SELECT count(*) FROM silver.V_HI_PROCINST_NODE WHERE PROC_STATE = 'TERMINATED'",
     "SELECT count(*) FROM silver.RMV_HI_PROCINST_NODE WHERE PROC_STATE = 'TERMINATED'",
     "流程層"),
    
    ("14. 平均流程歷時 (秒)",
     "SELECT round(avg(duration_seconds), 2) FROM flowable_analytics.silver_enriched_procinst WHERE duration_seconds IS NOT NULL",
     "SELECT round(avg(DURATION_SEC), 2) FROM silver.V_HI_PROCINST_NODE WHERE DURATION_SEC IS NOT NULL",
     "SELECT round(avg(DURATION_SEC), 2) FROM silver.RMV_HI_PROCINST_NODE WHERE DURATION_SEC IS NOT NULL",
     "流程層"),
    
    # === 業務事件層指標 ===
    ("15. 業務事件總數",
     None,  # 參考環境沒有對應表
     "SELECT count(*) FROM silver.V_HI_BIZ_EVENT_INFO",
     "SELECT count(*) FROM silver.RMV_HI_BIZ_EVENT_INFO",
     "業務事件層"),
    
    ("16. 在途業務事件數",
     None,
     "SELECT count(*) FROM silver.V_HI_BIZ_EVENT_INFO WHERE FINAL_END_TIME IS NULL",
     "SELECT count(*) FROM silver.RMV_HI_BIZ_EVENT_INFO WHERE FINAL_END_TIME IS NULL",
     "業務事件層"),
    
    ("17. 已完成業務事件數",
     None,
     "SELECT count(*) FROM silver.V_HI_BIZ_EVENT_INFO WHERE FINAL_END_TIME IS NOT NULL",
     "SELECT count(*) FROM silver.RMV_HI_BIZ_EVENT_INFO WHERE FINAL_END_TIME IS NOT NULL",
     "業務事件層"),
]

# 執行比較
print(f"\n{'指標':<35} | {'Benchmark':>15} | {'View':>15} | {'RMV':>15} | {'View vs Bench':>12} | {'View vs RMV':>10} | {'層級':<10}")
print("-" * 130)

results = []
for name, ref_sql, view_sql, rmv_sql, level in METRICS:
    # Benchmark
    if ref_sql:
        try:
            ref_val = ref_client.query(ref_sql).result_rows[0][0]
        except:
            ref_val = "ERR"
    else:
        ref_val = "N/A"
    
    # View
    try:
        view_val = my_client.query(view_sql).result_rows[0][0]
    except:
        view_val = "ERR"
    
    # RMV
    try:
        rmv_val = my_client.query(rmv_sql).result_rows[0][0]
    except:
        rmv_val = "ERR"
    
    # 比較
    if ref_val != "N/A" and ref_val != "ERR" and view_val != "ERR":
        if isinstance(ref_val, (int, float)) and isinstance(view_val, (int, float)):
            if ref_val == view_val:
                bench_cmp = "✅"
            else:
                diff_pct = abs(view_val - ref_val) / ref_val * 100 if ref_val != 0 else 0
                bench_cmp = f"⚠️ {diff_pct:.1f}%"
        else:
            bench_cmp = "?"
    else:
        bench_cmp = "-"
    
    if view_val != "ERR" and rmv_val != "ERR":
        if view_val == rmv_val:
            rmv_cmp = "✅"
        else:
            rmv_cmp = "⚠️"
    else:
        rmv_cmp = "?"
    
    # 格式化輸出
    ref_str = f"{ref_val:,}" if isinstance(ref_val, int) else str(ref_val)
    view_str = f"{view_val:,}" if isinstance(view_val, int) else str(view_val)
    rmv_str = f"{rmv_val:,}" if isinstance(rmv_val, int) else str(rmv_val)
    
    print(f"{name:<35} | {ref_str:>15} | {view_str:>15} | {rmv_str:>15} | {bench_cmp:>12} | {rmv_cmp:>10} | {level:<10}")
    
    results.append((name, ref_val, view_val, rmv_val, bench_cmp, rmv_cmp, level))

print("-" * 130)

# 統計
print("\n" + "=" * 80)
print("統計摘要")
print("=" * 80)

# View vs Benchmark
bench_match = sum(1 for r in results if r[4] == "✅")
bench_diff = sum(1 for r in results if "⚠️" in str(r[4]))
bench_na = sum(1 for r in results if r[4] == "-")
print(f"\nView vs Benchmark:")
print(f"  ✅ 一致: {bench_match}")
print(f"  ⚠️ 有差異: {bench_diff}")
print(f"  - 無法比較: {bench_na}")

# View vs RMV
rmv_match = sum(1 for r in results if r[5] == "✅")
rmv_diff = sum(1 for r in results if r[5] == "⚠️")
print(f"\nView vs RMV:")
print(f"  ✅ 一致: {rmv_match}")
print(f"  ⚠️ 有差異: {rmv_diff}")

# 差異說明
print("\n" + "=" * 80)
print("差異說明")
print("=" * 80)
print("""
1. View vs Benchmark 差異原因:
   - 參考環境有過濾條件 (TASK_DEF_KEY_ NOT LIKE 'E%'/'C%')
   - 資料同步時間點不同
   - 狀態名稱不同 (TERMINATED vs CANCELLED, RUNNING vs DOING, COMPLETED vs DONE)

2. View vs RMV 差異原因:
   - RMV 是每天刷新，View 是即時查詢
   - 如果有差異，表示今天有新資料進來

3. 業務事件層 (15-17):
   - 參考環境沒有對應的 gold_biz_event_summary 表可比較
   - 只能比較 View vs RMV
""")
