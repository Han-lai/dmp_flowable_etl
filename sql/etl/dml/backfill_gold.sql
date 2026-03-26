-- Phase 4: Gold Layer Aggregation (Time-Bounded)
-- Variables: {start_ts}, {end_ts}
-- Target: gold.rmv_l5_task_completion_phys (Physical ReplacingMergeTree)
--
-- ┌─ Milestone Architecture (2026-03-26 修正 v3) ──────────────────────────────┐
-- │ 1. milestone_stats: 每一天只看當天有發生 start/claim/end 的任務（互斥算 total）│
-- │ 2. acc_stats: 任務只要處於 Todo/Doing (start~end中間)，每天都算 1 筆在途   │
-- │ 關鍵是 snapshot_date 都必須限制在當前 `{start_ts}` ~ `{end_ts}` 窗口內。     │
-- └─────────────────────────────────────────────────────────────────────────────┘

INSERT INTO gold.rmv_l5_task_completion_phys
WITH
milestone_stats AS (
    SELECT
        snapshot_date,
        vx_type, region, plant, factory, line,
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
    WHERE is_excluded = 0
      AND snapshot_date >= toDate('{start_ts}')
      AND snapshot_date <= toDate('{end_ts}')
    GROUP BY snapshot_date, vx_type, region, plant, factory, line
),
acc_stats AS (
    -- 任務處於 7 天滑動視窗內的活躍狀態
    -- 對於每個任務，我們產生它「貢獻為在途」的 snapshot_date 陣列
    -- 條件：snapshot_date 必須 >= 任務開始日，且 <= start+6，且任務在該日尚未完成
    SELECT
        active_date AS snapshot_date,
        vx_type, region, plant, factory, line,
        uniqExact(task_id) AS acc_todo_doing
    FROM silver.mv_fact_task_vx FINAL
    ARRAY JOIN arrayMap(
        d -> toDate(d),
        range(
            toUInt32(task_start_date),
            toUInt32(least(
                COALESCE(task_end_date, today() + 2),
                task_start_date + 7,         -- 最多貢獻 7 天
                toDate('{end_ts}') + 1       -- 不超過運算窗口
            ))
        )
    ) AS active_date
    WHERE is_excluded = 0
      AND active_date >= toDate('{start_ts}')
      AND active_date <= toDate('{end_ts}')
      AND (task_end_date IS NULL OR task_end_date > active_date) -- 確保在 active_date 當下尚未完成
    GROUP BY active_date, vx_type, region, plant, factory, line
)

SELECT
    COALESCE(m.snapshot_date, a.snapshot_date) AS snapshot_date,
    COALESCE(m.vx_type, a.vx_type) AS vx_type,
    COALESCE(m.region, a.region) AS region,
    COALESCE(m.plant, a.plant) AS plant,
    COALESCE(m.factory, a.factory) AS factory,
    COALESCE(m.line, a.line) AS line,
    COALESCE(m.total_task, 0) AS total_task,
    COALESCE(m.todo_count, 0) AS todo_count,
    COALESCE(m.doing_count, 0) AS doing_count,
    COALESCE(m.done_count, 0) AS done_count,
    COALESCE(a.acc_todo_doing, 0) AS acc_todo_doing,
    now() AS _refresh_time
FROM milestone_stats m
FULL OUTER JOIN acc_stats a
    ON m.snapshot_date = a.snapshot_date
   AND m.vx_type = a.vx_type
   AND m.region = a.region
   AND m.plant = a.plant
   AND m.factory = a.factory
   AND m.line = a.line
