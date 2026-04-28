# -*- coding: utf-8 -*-
"""
Diagnose UI Discrepancy V4 - Verify ARRAY JOIN Behavior
READ-ONLY - No modifications
"""

import clickhouse_connect

client = clickhouse_connect.get_client(
    host='10.146.206.76',
    port=8123,
    username='default',
    password='1qaz2wsx3edc'
)

print("=" * 100)
print("ARRAY JOIN BEHAVIOR VERIFICATION - DG3/ST02 12-25")
print("=" * 100)

# ============================================================================
# Test 1: Verify arrayDistinct behavior
# ============================================================================
print("\n" + "=" * 100)
print("TEST 1: Verify arrayDistinct behavior")
print("=" * 100)

# Check if same-day dates are deduplicated
test_query = """
SELECT
    task_id,
    task_start_date,
    task_claim_date,
    task_end_date,
    arrayDistinct(arrayFilter(d -> d IS NOT NULL, [task_start_date, task_claim_date, task_end_date])) AS all_dates,
    length(arrayDistinct(arrayFilter(d -> d IS NOT NULL, [task_start_date, task_claim_date, task_end_date]))) AS unique_date_count
FROM silver.mv_fact_task_vx FINAL
WHERE plant = 'DG3' AND line = 'ST02' AND vx_type = 'V3'
  AND is_excluded = 0
  AND task_start_date = '2025-12-25'
  AND task_claim_date = '2025-12-25'
  AND task_end_date = '2025-12-25'
LIMIT 5
"""

result = client.query(test_query)
print("\n  Tasks where all 3 dates = 2025-12-25:")
print(f"  {'Task ID':<40} | {'Start':<12} | {'Claim':<12} | {'End':<12} | {'Unique Dates':<15}")
print("  " + "-" * 100)
for row in result.result_rows:
    print(f"  {row[0]:<40} | {str(row[1]):<12} | {str(row[2]):<12} | {str(row[3]):<12} | {row[4]} ({row[5]} unique)")

# ============================================================================
# Test 2: Simulate exact Gold layer query
# ============================================================================
print("\n" + "=" * 100)
print("TEST 2: Simulate exact Gold layer aggregation")
print("=" * 100)

gold_sim = """
SELECT
    snapshot_date,
    count()                                                                            AS total_task,
    countIf(snapshot_date < COALESCE(task_claim_date, task_end_date, today() + 1))    AS todo_count,
    countIf(
        task_claim_date IS NOT NULL
        AND snapshot_date >= task_claim_date
        AND (task_end_date IS NULL OR snapshot_date < task_end_date)
    )                                                                                  AS doing_count,
    countIf(task_end_date IS NOT NULL AND snapshot_date >= task_end_date)              AS done_count
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayDistinct(arrayFilter(
    d -> d IS NOT NULL,
    [task_start_date, task_claim_date, task_end_date]
)) AS snapshot_date
WHERE plant = 'DG3' AND line = 'ST02' AND vx_type = 'V3'
  AND is_excluded = 0
  AND snapshot_date = '2025-12-25'
GROUP BY snapshot_date
"""

result = client.query(gold_sim)
print("\n  Simulated Gold Layer Result:")
print(f"  {'Snapshot Date':<15} | {'Total':<10} | {'Todo':<10} | {'Doing':<10} | {'Done':<10}")
print("  " + "-" * 65)
for row in result.result_rows:
    print(f"  {str(row[0]):<15} | {row[1]:<10} | {row[2]:<10} | {row[3]:<10} | {row[4]:<10}")

print("\n  UI Expected: Total=265, Todo=66, Doing=36, Done=163")

# ============================================================================
# Test 3: Break down by how tasks reach 12-25 snapshot
# ============================================================================
print("\n" + "=" * 100)
print("TEST 3: Tasks reaching 12-25 snapshot - breakdown")
print("=" * 100)

# Tasks that contribute to 12-25 via ARRAY JOIN
breakdown = """
SELECT
    CASE
        WHEN has(arrayDistinct(arrayFilter(d -> d IS NOT NULL, [task_start_date, task_claim_date, task_end_date])), toDate('2025-12-25')) THEN 'Appears on 12-25'
        ELSE 'Does not appear on 12-25'
    END AS appears,
    CASE
        WHEN task_start_date = '2025-12-25' THEN 'Started on 12-25'
        WHEN task_claim_date = '2025-12-25' THEN 'Claimed on 12-25 (started earlier)'
        WHEN task_end_date = '2025-12-25' THEN 'Ended on 12-25 (started earlier)'
        ELSE 'N/A'
    END AS reach_method,
    count() AS cnt
FROM silver.mv_fact_task_vx FINAL
WHERE plant = 'DG3' AND line = 'ST02' AND vx_type = 'V3'
  AND is_excluded = 0
  AND (task_start_date = '2025-12-25' OR task_claim_date = '2025-12-25' OR task_end_date = '2025-12-25')
GROUP BY appears, reach_method
ORDER BY reach_method
"""

result = client.query(breakdown)
print(f"\n  {'Reach Method':<40} | {'Count':<10}")
print("  " + "-" * 55)
total = 0
for row in result.result_rows:
    print(f"  {row[1]:<40} | {row[2]:<10}")
    total += row[2]
print("  " + "-" * 55)
print(f"  {'Total Unique Tasks':<40} | {total:<10}")

# ============================================================================
# Test 4: UI uses task_start_date only?
# ============================================================================
print("\n" + "=" * 100)
print("TEST 4: If UI counts only task_start_date = 12-25")
print("=" * 100)

start_only = """
SELECT
    count() AS total,
    -- Status at snapshot = task_start_date
    countIf(task_claim_date IS NULL OR task_start_date < task_claim_date) AS todo,
    countIf(task_claim_date IS NOT NULL AND task_start_date >= task_claim_date AND (task_end_date IS NULL OR task_start_date < task_end_date)) AS doing,
    countIf(task_end_date IS NOT NULL AND task_start_date >= task_end_date) AS done
FROM silver.mv_fact_task_vx FINAL
WHERE plant = 'DG3' AND line = 'ST02' AND vx_type = 'V3'
  AND is_excluded = 0
  AND task_start_date = '2025-12-25'
"""

result = client.query(start_only)
row = result.result_rows[0]
print(f"\n  Counting by task_start_date = 12-25:")
print(f"  Total: {row[0]}, Todo: {row[1]}, Doing: {row[2]}, Done: {row[3]}")
print(f"\n  UI Expected: Total=265, Todo=66, Doing=36, Done=163")
print(f"  Match: Total={'YES' if row[0] == 265 else 'NO (' + str(row[0] - 265) + ')'}")

# ============================================================================
# Test 5: What if UI counts task_start_date for status determination?
# ============================================================================
print("\n" + "=" * 100)
print("TEST 5: Different status calculation approaches")
print("=" * 100)

# Approach: Count all tasks touching 12-25, status based on actual dates
approach_query = """
SELECT
    CASE
        WHEN task_start_date = '2025-12-25' AND (task_claim_date IS NULL OR task_claim_date > '2025-12-25') THEN 'Todo'
        WHEN task_claim_date = '2025-12-25' AND (task_end_date IS NULL OR task_end_date > '2025-12-25') THEN 'Doing'
        WHEN task_end_date = '2025-12-25' THEN 'Done'
        WHEN task_start_date = '2025-12-25' AND task_claim_date = '2025-12-25' AND (task_end_date IS NULL OR task_end_date > '2025-12-25') THEN 'Doing'
        WHEN task_start_date = '2025-12-25' AND task_claim_date = '2025-12-25' AND task_end_date = '2025-12-25' THEN 'Done'
        WHEN task_start_date < '2025-12-25' AND task_claim_date = '2025-12-25' THEN 'Doing'
        WHEN task_start_date < '2025-12-25' AND task_end_date = '2025-12-25' THEN 'Done'
        ELSE 'Unknown'
    END AS status,
    count() AS cnt
FROM silver.mv_fact_task_vx FINAL
WHERE plant = 'DG3' AND line = 'ST02' AND vx_type = 'V3'
  AND is_excluded = 0
  AND (task_start_date = '2025-12-25' OR task_claim_date = '2025-12-25' OR task_end_date = '2025-12-25')
GROUP BY status
ORDER BY status
"""

result = client.query(approach_query)
print("\n  Priority-based status assignment:")
print(f"  {'Status':<15} | {'Count':<10}")
print("  " + "-" * 30)
total = 0
for row in result.result_rows:
    print(f"  {row[0]:<15} | {row[1]:<10}")
    total += row[1]
print("  " + "-" * 30)
print(f"  Total: {total}")
print(f"\n  UI Expected: Total=265, Todo=66, Doing=36, Done=163")

# ============================================================================
# Test 6: Check if UI uses DISTINCT counting
# ============================================================================
print("\n" + "=" * 100)
print("TEST 6: If UI uses task_start_date for counting, different status logic")
print("=" * 100)

# Perhaps UI counts tasks that START on 12-25, but uses different status
ui_logic = """
SELECT
    -- Status AT the end of 12-25 (final status of tasks that started on 12-25)
    CASE
        WHEN task_end_date <= '2025-12-25' THEN 'Done'
        WHEN task_claim_date IS NOT NULL AND task_claim_date <= '2025-12-25' THEN 'Doing'
        ELSE 'Todo'
    END AS status_at_eod,
    count() AS cnt
FROM silver.mv_fact_task_vx FINAL
WHERE plant = 'DG3' AND line = 'ST02' AND vx_type = 'V3'
  AND is_excluded = 0
  AND task_start_date = '2025-12-25'
GROUP BY status_at_eod
ORDER BY status_at_eod
"""

result = client.query(ui_logic)
print("\n  Tasks starting on 12-25, status at end of day:")
print(f"  {'Status':<15} | {'Count':<10}")
print("  " + "-" * 30)
for row in result.result_rows:
    print(f"  {row[0]:<15} | {row[1]:<10}")
print(f"\n  UI Expected: Total=265, Todo=66, Doing=36, Done=163")

print("\n" + "=" * 100)
print("FINAL DIAGNOSIS")
print("=" * 100)
