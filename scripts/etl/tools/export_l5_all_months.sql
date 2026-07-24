-- =====================================================================
-- L5 UAT 對帳明細：一次匯出全部月份 × 五階 × vx_type 到 S3
-- =====================================================================
-- 用途：產生給 UAT 測試員逐格對帳用的明細檔，內容必須能精確重現報表畫面數字。
--       單月／單線體的匯出請改用 scripts/etl/tools/export_l5_to_s3.sh。
--
-- 執行前替換三個佔位符（勿寫死進版控）：
--   <S3_ENDPOINT>  例：http://your-s3-host
--   <S3_BUCKET>    例：your-bucket
--   <S3_AK> / <S3_SK>
--
-- 產出檔名：{年-月}_{region}_{plant}_{vx_type}.csv.gz
--          例：2026-03_CNE_WJ2_V1.csv.gz
--
-- ---------------------------------------------------------------------
-- 【核心：為什麼要 ARRAY JOIN 展開多個月份】
-- ---------------------------------------------------------------------
-- Gold 的「日」粒度在 2026-04-01 前後是兩套語意（見 backfill_gold_summary*.sql）：
--
--   < 2026-04-01  事件日語意：當天有「任何動作」的任務都算
--                 → snapshot_date 由 [start, claim, end] 三個日期展開
--                 → 一筆 2 月開單、3/31 完工的任務，要出現在【三月】的檔案裡
--
--   >= 2026-04-01 開單日 cohort：只算當天開單的任務
--                 → 只需開單月那一列
--
-- 若沿用 PARTITION BY formatDateTime(task_start_date,'%Y-%m')，跨月任務會被
-- 丟回開單月的檔案，該月明細就湊不出畫面數字。
-- （實例：2026-03 CNE/WJ2 V1，3/31 畫面 2,615，只按開單日篩只有 1,680；
--   補進 26 筆他月開單、3/31 完工的任務後才精確等於 2,615。）
--
-- 因此 ym_list 的規則是：
--   開單月一律進；簽收月／完工月只有在 < 2026-04 時才進。
--
-- ---------------------------------------------------------------------
-- 【產出欄位：38 欄】
-- ---------------------------------------------------------------------
--   A..AJ  原 36 欄（status_weekly / status_monthly 已就地重算，見下方說明）
--   AK     in_month_cohort  1=本月開單，0=他月開單的跨月補列
--                           ※ 週／月粒度對帳務必加 AK=1，否則會多算
--   AL     file_month       這一列屬於哪個月的檔案（除錯用）
--
-- 對帳公式對照（測試案例 L5-DAY-001 / L5-DAY-002 / L5-RECON-001）：
--   日粒度 < 2026-04-01 ：三個日期任一 = D
--   日粒度 >= 2026-04-01：只看 task_start_date = D
--   月粒度（兩側共用）  ：COUNTIF(AK:AK,1) 系列
--
-- ---------------------------------------------------------------------
-- 【status_weekly / status_monthly 就地重算】
-- ---------------------------------------------------------------------
-- silver 的存欄位在 2026-07-23 (74e33ac) 之前有 1970 哨兵 bug：未完工任務的
-- END_TIME_ 為 1970-01-01 而非 NULL，`1970 <= 週底/月底` 恆成立 → 全被誤標 DONE。
-- SQL 已修，但既有資料需重跑 silver 才會更新，故此處以 NULL-aware 欄位重算，
-- 與 gold milestone 對齊。silver 重建後此段仍可保留作為防禦。
-- status_daily 用 `=` 比較，不受該 bug 影響，維持直接輸出。
--
-- ---------------------------------------------------------------------
-- 【驗證記錄】CNE/WJ2，2025-10-08 ~ 2026-05-25，664 組（日期 × vx）
--   對 gold.rmv_l5_task_summary 逐日比對 Total/Todo/Doing/Done：真實差異 0 筆。
--   另有 21 組為 Gold 的「零開單日補丁」(total=0)，明細檔無列，數值同為 0。
-- =====================================================================

INSERT INTO FUNCTION s3(
    '<S3_ENDPOINT>/<S3_BUCKET>/DMP_KPI/{_partition_id}.csv.gz',
    '<S3_AK>', '<S3_SK>', 'CSVWithNames')
PARTITION BY concat(file_month, '_', region, '_', plant, '_', vx_type)
SELECT
    * EXCEPT (ym_start, ym_list),
    if(file_month = ym_start, 1, 0) AS in_month_cohort,
    file_month                          -- 必須留在 SELECT，否則 PARTITION BY 取不到
FROM (
    SELECT
        * EXCEPT (task_primary_date, task_create_date, ui_time_field,
                  _mview_update_time, task_status)
          REPLACE (
            CASE WHEN task_end_date   IS NOT NULL
                  AND task_end_date   <= (toStartOfWeek(task_start_date, 3) + INTERVAL 6 DAY) THEN 'DONE'
                 WHEN task_claim_date IS NOT NULL
                  AND task_claim_date <= (toStartOfWeek(task_start_date, 3) + INTERVAL 6 DAY) THEN 'DOING'
                 ELSE 'TODO' END AS status_weekly,
            CASE WHEN task_end_date   IS NOT NULL
                  AND task_end_date   <= toLastDayOfMonth(task_start_date) THEN 'DONE'
                 WHEN task_claim_date IS NOT NULL
                  AND task_claim_date <= toLastDayOfMonth(task_start_date) THEN 'DOING'
                 ELSE 'TODO' END AS status_monthly),

        formatDateTime(task_start_date, '%Y-%m') AS ym_start,

        -- 這筆任務要出現在哪些月份的檔案
        arrayDistinct(arrayConcat(
            [formatDateTime(task_start_date, '%Y-%m')],
            arrayFilter(m -> m != '' AND m < '2026-04', [
                ifNull(formatDateTime(task_claim_date, '%Y-%m'), ''),
                ifNull(formatDateTime(task_end_date,   '%Y-%m'), '')
            ])
        )) AS ym_list

    FROM silver.mv_fact_task_vx FINAL
    WHERE is_excluded = 0
)
ARRAY JOIN ym_list AS file_month
SETTINGS max_partitions_per_insert_block = 500;


-- =====================================================================
-- 匯出後對帳（把 <YM> / <REGION> / <PLANT> / <DAY> 換成要驗的值）
-- =====================================================================
--
-- [1] 日粒度，< 2026-04-01（事件日語意）——應等於畫面 Day 該列
-- SELECT vx_type,
--        countIf(task_start_date = '<DAY>' OR task_claim_date = '<DAY>' OR task_end_date = '<DAY>') AS total,
--        countIf(task_start_date = '<DAY>' AND (task_claim_date IS NULL OR task_claim_date != '<DAY>')
--                                          AND (task_end_date   IS NULL OR task_end_date   != '<DAY>')) AS todo,
--        countIf(task_claim_date = '<DAY>' AND (task_end_date IS NULL OR task_end_date != '<DAY>'))     AS doing,
--        countIf(task_end_date = '<DAY>')                                                               AS done
-- FROM <匯出結果> WHERE file_month = '<YM>' GROUP BY vx_type ORDER BY vx_type;
--
-- [2] 日粒度，>= 2026-04-01（開單日 cohort）
-- 同上但只看 task_start_date = '<DAY>'，並加 in_month_cohort = 1。
--
-- [3] 月粒度（兩側共用）
-- SELECT vx_type, count(), countIf(status_monthly='TODO'),
--        countIf(status_monthly='DOING'), countIf(status_monthly='DONE')
-- FROM <匯出結果> WHERE file_month = '<YM>' AND in_month_cohort = 1
-- GROUP BY vx_type ORDER BY vx_type;
--
-- [4] 對照 Gold
-- SELECT vx_type, sum(total_qty), sum(todo_qty), sum(doing_qty), sum(done_qty)
-- FROM gold.rmv_l5_task_summary FINAL
-- WHERE period_type = 'Day' AND period_key = '<DAY>'
--   AND region = '<REGION>' AND plant = '<PLANT>'
-- GROUP BY vx_type ORDER BY vx_type;
-- =====================================================================
