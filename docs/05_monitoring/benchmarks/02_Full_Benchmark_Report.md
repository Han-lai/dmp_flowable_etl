# L5 ClickHouse 效能基準測試報告

- **測試日期**：2026-03-06
- **測試環境**：ClickHouse 容器內部（排除 Docker Network 延遲）
- **測試工具**：`clickhouse-benchmark`（ClickHouse 官方 CLI Benchmark Tool）
- **測試 SQL**：`stress_test_l5_pivot.py` / `stress_test_wj2_pivot.py` 產生，與 Superset Cube.js Pivot Model 完全一致
- **原始測試輸出**：`04_Raw_Test_Logs.md`

---

## 1. 測試參數

| 參數 | 值 |
| :--- | :--- |
| Concurrency | 10 |
| Iterations | 100 |
| Randomize | Enabled |
| Target Table | `gold.rmv_l5_task_completion_v2` |
| Data Range | 2025-12-25 至 2025-12-31（7 天） |

| 測試組 | 條件 | SQL 檔案 |
| :--- | :--- | :--- |
| **A** | V3 / CNS / DG3 / SMT / ST02 | `queries_dg3_pivot.sql` / `queries_dg3_standard.sql` |
| **B** | V3 / CNE / WJ2 / NBU / E5 | `queries_wj2_pivot.sql` / `queries_wj2_standard.sql` |

---

## 2. 資料正確性驗證

### 2.1 測試組 A：DG3 / SMT / ST02（Month 粒度，12/01 ~ 12/25）

| 欄位 | 直接 GROUP BY | Pivot SQL CTE | 比對 |
| :--- | :--- | :--- | :--- |
| total_task | 5,611 | 5,611 | MATCH |
| todo_count | 1,288 | 1,288 | MATCH |
| doing_count | 1,220 | 1,220 | MATCH |
| done_count | 3,103 | 3,103 | MATCH |

逐日明細（12/25 ~ 12/31）：

| snapshot_date | total_task | todo_count | doing_count | done_count | acc_todo_doing |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-12-25 | 306 | 66 | 36 | 204 | 154 |
| 2025-12-26 | 178 | 19 | 66 | 93 | 171 |
| 2025-12-27 | 291 | 22 | 29 | 240 | 97 |
| 2025-12-28 | 12 | 1 | 1 | 10 | 91 |
| 2025-12-29 | 147 | 64 | 28 | 55 | 134 |
| 2025-12-30 | 128 | 7 | 53 | 68 | 102 |
| 2025-12-31 | 49 | 3 | 8 | 38 | 69 |

### 2.2 測試組 B：WJ2 / NBU / E5（Month 粒度，12/01 ~ 12/31）

| 欄位 | 直接 GROUP BY | Pivot SQL CTE | 比對 |
| :--- | :--- | :--- | :--- |
| total_task | 2,808 | 2,808 | MATCH |
| todo_count | 308 | 308 | MATCH |
| doing_count | 235 | 235 | MATCH |
| done_count | 2,263 | 2,263 | MATCH |

逐日明細（12/25 ~ 12/31）：

| snapshot_date | total_task | todo_count | doing_count | done_count | acc_todo_doing |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-12-25 | 192 | 26 | 1 | 165 | 41 |
| 2025-12-26 | 148 | 56 | 12 | 80 | 77 |
| 2025-12-27 | 110 | 14 | 4 | 92 | 45 |
| 2025-12-28 | 11 | 3 | 0 | 8 | 47 |
| 2025-12-29 | 88 | 3 | 22 | 63 | 44 |
| 2025-12-30 | 264 | 8 | 60 | 196 | 96 |
| 2025-12-31 | 211 | 9 | 5 | 197 | 99 |

---

## 3. 查詢延遲與吞吐量

### 3.1 Pivot Model（端到端，含 6× UNION ALL 轉置）

| 指標 | A：DG3/SMT/ST02 | B：WJ2/NBU/E5 | 判定基準 | A 結果 | B 結果 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| QPS | 10.5 queries/sec | 12.4 queries/sec | > 10 | **PASS** | **PASS** |
| P50 Latency | 878 ms | 739 ms | — | — | — |
| P95 Latency | 1,208 ms | 1,000 ms | < 1,000 ms | **FAIL** | **MARGINAL** |
| P99.9 Latency | 1,349 ms | 1,089 ms | — | — | — |
| Throughput | 390 MiB/sec | 459 MiB/sec | — | — | — |

### 3.2 Standard Model（純聚合，無 Pivot 轉置）

| 指標 | A：DG3/SMT/ST02 | B：WJ2/NBU/E5 | 判定基準 | A 結果 | B 結果 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| QPS | 62.2 queries/sec | 51.4 queries/sec | > 10 | **PASS** | **PASS** |
| P50 Latency | 139 ms | 169 ms | — | — | — |
| P95 Latency | 196 ms | 258 ms | < 1,000 ms | **PASS** | **PASS** |
| P99.9 Latency | 264 ms | 300 ms | — | — | — |

---

## 4. 資料壓縮比

資料來源：`system.parts WHERE active = 1`，涵蓋 Bronze / Silver / Gold 全層。

| # | database | table | Uncompressed | Compressed | Ratio | Rows |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | bronze | `bpm_act_hi_varinst` | 4.70 GiB | 729.95 MiB | 6.60x | 17,345,207 |
| 2 | bronze | `bpm_act_hi_taskinst` | 524.16 MiB | 142.89 MiB | 3.67x | 1,472,565 |
| 3 | bronze | `bpm_act_hi_procinst` | 216.52 MiB | 54.68 MiB | 3.96x | 532,554 |
| 4 | bronze | `bpm_act_hi_identitylink` | 204.67 MiB | 20.28 MiB | 10.09x | 1,239,084 |
| 5 | bronze | `common_flowable_task_stats` | 145.71 MiB | 26.67 MiB | 5.46x | 389,049 |
| 6 | bronze | `common_hr_employee` | 75.60 MiB | 19.68 MiB | 3.84x | 127,436 |
| 7 | gold | `rmv_user_utilization_data` | 2.72 MiB | 78.18 KiB | 35.61x | 50,735 |
| 8 | gold | `rmv_l5_task_completion_data` | 897.87 KiB | 249.25 KiB | 3.60x | 10,704 |
| 9 | gold | `rmv_l5_task_completion_v2_data` | 897.87 KiB | 249.25 KiB | 3.60x | 10,704 |

> 備註：Silver 層中以 `.inner_id.*` 命名之表為 Materialized View 內部儲存，壓縮比介於 3.14x ~ 6.73x。完整 33 張表清單見 `04_Raw_Test_Logs.md` Test 7。

---

## 5. Per-Query 資源消耗

資料來源：`system.query_log`（`type = 'QueryFinish'`，涉及 `gold.rmv_l5_task_completion_v2`）。

| 指標 | 欄位來源 | 平均值 | 峰值 |
| :--- | :--- | :--- | :--- |
| Query Duration | `query_duration_ms` | 488.3 ms | 2,080 ms |
| Memory Usage | `memory_usage` | 240.71 MiB | 404.10 MiB |
| CPU Time (User) | `ProfileEvents['UserTimeMicroseconds']` | 257.9 ms | 793.4 ms |

樣本數：786 次查詢（涵蓋 Test 1 ~ Test 6 期間所有 L5 相關查詢）。

---

## 6. 瓶頸定位

| 層級 | A：DG3/SMT (P50) | A 佔比 | B：WJ2/E5 (P50) | B 佔比 |
| :--- | :--- | :--- | :--- | :--- |
| Standard Model（聚合） | 139 ms | 15.8% | 169 ms | 22.9% |
| Pivot 轉置（6× UNION ALL） | 739 ms | 84.2% | 570 ms | 77.1% |
| **Pivot Model（端到端）** | **878 ms** | **100%** | **739 ms** | **100%** |

兩組測試之 Standard Model P95 均低於 300 ms，確認瓶頸為 Cube.js Pivot Model 之 6 段 `UNION ALL` 行列轉置，非 ClickHouse MergeTree 引擎。

---

## 7. 驗收結論

| 驗收項目 | A：DG3/SMT/ST02 | B：WJ2/NBU/E5 | 判定基準 | A 結果 | B 結果 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 資料正確性 | 4/4 MATCH | 4/4 MATCH | 全欄位一致 | **PASS** | **PASS** |
| 逐日明細完整性 | 7/7 天 | 7/7 天 | 12/25~12/31 無缺漏 | **PASS** | **PASS** |
| QPS（Pivot, 10 Concurrency） | 10.5 queries/sec | 12.4 queries/sec | > 10 | **PASS** | **PASS** |
| P95 Latency（Pivot） | 1,208 ms | 1,000 ms | < 1,000 ms | **FAIL** | **MARGINAL** |
| P95 Latency（Standard） | 196 ms | 258 ms | < 1,000 ms | **PASS** | **PASS** |
| 壓縮比（Bronze 主表） | 6.60x | 6.60x | > 3x | **PASS** | **PASS** |
| Peak Memory（單次查詢） | 404.10 MiB | 404.10 MiB | < 1 GiB | **PASS** | **PASS** |
| Peak CPU（單次查詢） | 793.4 ms | 793.4 ms | — | — | — |
