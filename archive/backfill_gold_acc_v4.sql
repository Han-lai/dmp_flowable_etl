-- Phase 4b (V4.1): Gold Layer ACC Aggregation (Same-day Cohort WIP)
-- 目的: 統計「過去 7 天內新開單，且目前尚未結案」的任務總數
-- 變數: {start_ts}, {end_ts}

INSERT INTO gold.rmv_l5_acc_v4_phys
SELECT
    toDate(active_date_raw) AS snapshot_date,
    vx_type, region, plant, factory, line,
    groupBitmapState(cityHash64(task_id)) AS acc,
    now() AS _refresh_time
FROM silver.mv_fact_task_vx_v4 FINAL
ARRAY JOIN arrayDistinct(
    -- 僅從 task_start_date 開始展開，且限制在開單後的 7 天內
    range(toUInt32(task_start_date), toUInt32(least(COALESCE(task_end_date, today() + 1), task_start_date + 7)))
) AS active_date_raw
WHERE is_excluded = 0
  AND toDate(active_date_raw) >= toDate('{start_ts}')
  AND toDate(active_date_raw) <= toDate('{end_ts}')
  -- 排除已經結案的狀態 (只抓 Todo + Doing)
  -- 根據 V4 邏輯，如果當天開單當天結案，則不應進入 ACC (因為它是純 Done)
  -- 這裡透過 task_end_date > active_date 確保排除掉當天完工的任務
  AND (task_end_date IS NULL OR task_end_date > toDate(active_date_raw))
GROUP BY snapshot_date, vx_type, region, plant, factory, line;
