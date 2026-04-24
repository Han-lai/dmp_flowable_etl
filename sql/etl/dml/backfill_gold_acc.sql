-- Phase 4b (V3): Gold Layer ACC Aggregation (7-Day Rolling Bitmap)
-- 目的: 實現 7 天滑動視窗 (Rolling 7D) 的在途任務統計
-- 變數: {start_ts}, {end_ts}

INSERT INTO gold.rmv_l5_acc_phys
SELECT
    active_date AS snapshot_date,
    vx_type, region, plant, factory, line,
    -- 統計在該基準日 D 往前推 6 天內曾活動且未結案的任務
    groupBitmapState(cityHash64(task_id)) AS acc,
    now() AS _refresh_time
FROM silver.mv_fact_task_vx FINAL
ARRAY JOIN arrayMap(
    d -> toDate(d),
    range(
        toUInt32(task_start_date),
        toUInt32(least(
            COALESCE(task_end_date, today() + 1),
            task_start_date + 7, -- 限制 7 天滑動窗口
            toDate('{end_ts}') + 1
        ))
    )
) AS active_date
WHERE is_excluded = 0
  AND active_date >= toDate('{start_ts}')
  AND active_date <= toDate('{end_ts}')
  AND (task_end_date IS NULL OR task_end_date > active_date)
GROUP BY active_date, vx_type, region, plant, factory, line;
