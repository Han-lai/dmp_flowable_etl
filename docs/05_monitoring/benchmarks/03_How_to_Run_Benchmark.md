# L5 ClickHouse 壓測執行手冊

依序於 **Portainer Console (ClickHouse Container)** 中執行。

---

## 前置作業：上傳 SQL 檔案

### A 組 Pivot（DG3/SMT）

```bash
cat << 'ENDOFSQL' > /tmp/benchmark/queries_dg3_pivot.sql
<貼上 D:\kiro\dmp_flowable\scripts\validation\queries_dg3_pivot.sql 的完整內容>
ENDOFSQL
```

### A 組 Standard（DG3/SMT）

```bash
cat << 'ENDOFSQL' > /tmp/benchmark/queries_dg3_standard.sql
<貼上 D:\kiro\dmp_flowable\scripts\validation\queries_dg3_standard.sql 的完整內容>
ENDOFSQL
```

### B 組 Pivot（WJ2/NBU/E5）

```bash
cat << 'ENDOFSQL' > /tmp/benchmark/queries_wj2_pivot.sql
<貼上 D:\kiro\dmp_flowable\scripts\validation\queries_wj2_pivot.sql 的完整內容>
ENDOFSQL
```

### B 組 Standard（WJ2/NBU/E5）

```bash
cat << 'ENDOFSQL' > /tmp/benchmark/queries_wj2_standard.sql
<貼上 D:\kiro\dmp_flowable\scripts\validation\queries_wj2_standard.sql 的完整內容>
ENDOFSQL
```

---

## Test 1：A 組 Pivot 壓測

```bash
clickhouse-benchmark --host=127.0.0.1 --port=9000 --user=default --password=default --concurrency=10 --iterations=100 --randomize < /tmp/benchmark/queries_dg3_pivot.sql 2>&1 | tee /tmp/benchmark/benchmark_dg3_pivot.txt
```

---

## Test 2：A 組 Standard 壓測

```bash
clickhouse-benchmark --host=127.0.0.1 --port=9000 --user=default --password=default --concurrency=10 --iterations=100 --randomize < /tmp/benchmark/queries_dg3_standard.sql 2>&1 | tee /tmp/benchmark/benchmark_dg3_standard.txt
```

---

## Test 3：B 組 Pivot 壓測

```bash
clickhouse-benchmark --host=127.0.0.1 --port=9000 --user=default --password=default --concurrency=10 --iterations=100 --randomize < /tmp/benchmark/queries_wj2_pivot.sql 2>&1 | tee /tmp/benchmark/benchmark_wj2_pivot.txt
```

---

## Test 4：B 組 Standard 壓測

```bash
clickhouse-benchmark --host=127.0.0.1 --port=9000 --user=default --password=default --concurrency=10 --iterations=100 --randomize < /tmp/benchmark/queries_wj2_standard.sql 2>&1 | tee /tmp/benchmark/benchmark_wj2_standard.txt
```

---

## Test 5：A 組資料正確性（V3/DG3/SMT/ST02 @ 12月整月）

直接 GROUP BY：

```bash
clickhouse-client --host=127.0.0.1 --user=default --password=default -q "
SELECT sum(total_task) AS total, sum(todo_count) AS todo, sum(doing_count) AS doing, sum(done_count) AS done
FROM gold.rmv_l5_task_completion_v2 FINAL
WHERE snapshot_date >= toDate('2025-12-01') AND snapshot_date <= toDate('2025-12-25')
  AND vx_type='V3' AND region='CNS' AND plant='DG3' AND factory='SMT' AND line='ST02'
FORMAT PrettyCompact"
```

Pivot SQL CTE Month：

```bash
clickhouse-client --host=127.0.0.1 --user=default --password=default -q "
WITH params AS (SELECT max(snapshot_date) AS mfd, today() AS st FROM gold.rmv_l5_task_completion_v2 WHERE snapshot_date=toDate('2025-12-25') AND vx_type='V3' AND region='CNS' AND plant='DG3' AND factory='SMT' AND line='ST02'),
ca AS (SELECT CASE WHEN mfd>=st THEN st ELSE mfd END AS anchor_dt, st FROM params),
base AS (SELECT * FROM gold.rmv_l5_task_completion_v2 CROSS JOIN ca WHERE snapshot_date>=toStartOfMonth(anchor_dt)-INTERVAL 1 MONTH AND snapshot_date<=toLastDayOfMonth(anchor_dt)+INTERVAL 1 MONTH AND vx_type='V3' AND region='CNS' AND plant='DG3' AND factory='SMT' AND line='ST02')
SELECT sum(total_task) AS total, sum(todo_count) AS todo, sum(doing_count) AS doing, sum(done_count) AS done
FROM base CROSS JOIN ca WHERE snapshot_date>=toStartOfMonth(anchor_dt) AND snapshot_date<=anchor_dt
GROUP BY vx_type,region,plant,factory,line,anchor_dt FORMAT PrettyCompact"
```

預期：`total=5611, todo=1288, doing=1220, done=3103`，兩組一致 = MATCH

逐日明細（12/25～12/31）：

```bash
clickhouse-client --host=127.0.0.1 --user=default --password=default -q "
SELECT snapshot_date, total_task, todo_count, doing_count, done_count, acc_todo_doing
FROM gold.rmv_l5_task_completion_v2 FINAL
WHERE snapshot_date >= toDate('2025-12-25') AND snapshot_date <= toDate('2025-12-31')
  AND vx_type='V3' AND region='CNS' AND plant='DG3' AND factory='SMT' AND line='ST02'
ORDER BY snapshot_date FORMAT PrettyCompact"
```

---

## Test 6：B 組資料正確性（V3/WJ2/NBU/E5 @ 12月整月）

直接 GROUP BY：

```bash
clickhouse-client --host=127.0.0.1 --user=default --password=default -q "
SELECT sum(total_task) AS total, sum(todo_count) AS todo, sum(doing_count) AS doing, sum(done_count) AS done
FROM gold.rmv_l5_task_completion_v2 FINAL
WHERE snapshot_date >= toDate('2025-12-01') AND snapshot_date <= toDate('2025-12-31')
  AND vx_type='V3' AND region='CNE' AND plant='WJ2' AND factory='NBU' AND line='E5'
FORMAT PrettyCompact"
```

Pivot SQL CTE Month：

```bash
clickhouse-client --host=127.0.0.1 --user=default --password=default -q "
WITH params AS (SELECT max(snapshot_date) AS mfd, today() AS st FROM gold.rmv_l5_task_completion_v2 WHERE snapshot_date=toDate('2025-12-31') AND vx_type='V3' AND region='CNE' AND plant='WJ2' AND factory='NBU' AND line='E5'),
ca AS (SELECT CASE WHEN mfd>=st THEN st ELSE mfd END AS anchor_dt, st FROM params),
base AS (SELECT * FROM gold.rmv_l5_task_completion_v2 CROSS JOIN ca WHERE snapshot_date>=toStartOfMonth(anchor_dt)-INTERVAL 1 MONTH AND snapshot_date<=toLastDayOfMonth(anchor_dt)+INTERVAL 1 MONTH AND vx_type='V3' AND region='CNE' AND plant='WJ2' AND factory='NBU' AND line='E5')
SELECT sum(total_task) AS total, sum(todo_count) AS todo, sum(doing_count) AS doing, sum(done_count) AS done
FROM base CROSS JOIN ca WHERE snapshot_date>=toStartOfMonth(anchor_dt) AND snapshot_date<=anchor_dt
GROUP BY vx_type,region,plant,factory,line,anchor_dt FORMAT PrettyCompact"
```

預期：`total=2808, todo=308, doing=235, done=2263`，兩組一致 = MATCH

逐日明細（12/25～12/31）：

```bash
clickhouse-client --host=127.0.0.1 --user=default --password=default -q "
SELECT snapshot_date, total_task, todo_count, doing_count, done_count, acc_todo_doing
FROM gold.rmv_l5_task_completion_v2 FINAL
WHERE snapshot_date >= toDate('2025-12-25') AND snapshot_date <= toDate('2025-12-31')
  AND vx_type='V3' AND region='CNE' AND plant='WJ2' AND factory='NBU' AND line='E5'
ORDER BY snapshot_date FORMAT PrettyCompact"
```

---

## Test 7：資料壓縮比

```bash
clickhouse-client --host=127.0.0.1 --user=default --password=default -q "
SELECT database, table,
  formatReadableSize(sum(data_uncompressed_bytes)) AS uncompressed,
  formatReadableSize(sum(data_compressed_bytes)) AS compressed,
  round(sum(data_uncompressed_bytes)/sum(data_compressed_bytes),2) AS ratio,
  sum(rows) AS rows
FROM system.parts WHERE active=1 AND database IN ('bronze','silver','gold')
GROUP BY database, table ORDER BY sum(data_uncompressed_bytes) DESC
FORMAT PrettyCompact"
```

---

## Test 8：Per-Query CPU / Memory（全部壓測完成後執行）

```bash
clickhouse-client --host=127.0.0.1 --user=default --password=default -q "
SELECT count() AS queries,
  round(avg(query_duration_ms),1) AS avg_ms, max(query_duration_ms) AS max_ms,
  formatReadableSize(avg(memory_usage)) AS avg_mem, formatReadableSize(max(memory_usage)) AS max_mem,
  round(avg(ProfileEvents['UserTimeMicroseconds'])/1000,1) AS avg_cpu_ms,
  round(max(ProfileEvents['UserTimeMicroseconds'])/1000,1) AS max_cpu_ms
FROM system.query_log
WHERE type='QueryFinish' AND query_kind='Select' AND event_date=today()
  AND query LIKE '%gold.rmv_l5_task_completion_v2%'
FORMAT PrettyCompact"
```

---

## 執行順序總覽

| # | 測試 | 報告 Section |
| :--- | :--- | :--- |
| 0 | 上傳 4 份 SQL 至 `/tmp/benchmark/` | — |
| 1 | A 組 Pivot 壓測 | §3 |
| 2 | A 組 Standard 壓測 | §6 |
| 3 | B 組 Pivot 壓測 | §3 |
| 4 | B 組 Standard 壓測 | §6 |
| 5 | A 組資料正確性 + 逐日明細 | §2 |
| 6 | B 組資料正確性 + 逐日明細 | §2 |
| 7 | 壓縮比 | §4 |
| 8 | CPU / Memory | §5 |
