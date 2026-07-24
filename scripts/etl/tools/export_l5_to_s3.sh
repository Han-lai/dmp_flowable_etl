#!/usr/bin/env bash
# 依五階+月份篩選 L5 明細，依 vx_type 切檔壓縮寫出 .csv.gz 到 S3（CH server 端執行）。
# 用法(廠級): S3_AK=.. S3_SK=.. YM=2026-03 REGION=CNE PLANT=WJ2 ./export_l5_to_s3.sh
# 用法(線級): 再加 FACTORY=NBU LINE=E5
#   FACTORY / LINE 留空 = 不下該層條件，檔名也不帶（UAT 對帳用的廠級檔即為此形式）
# 可選: S3_ENDPOINT / S3_BUCKET / S3_PREFIX / CH_CONTAINER / DRY_RUN=1
set -euo pipefail

YM=${YM:?例 2026-04}
REGION=${REGION:?例 CNE}
PLANT=${PLANT:?例 WJ2}
FACTORY=${FACTORY:-}
LINE=${LINE:-}
S3_AK=${S3_AK:?}
S3_SK=${S3_SK:?}

# endpoint / bucket 一律由環境變數提供，不寫死內部位址（也避免預設值猜錯而寫到別的 bucket）
S3_ENDPOINT=${S3_ENDPOINT:?例 http://your-s3-host}
S3_BUCKET=${S3_BUCKET:?例 your-bucket}
S3_PREFIX=${S3_PREFIX:-DMP_KPI}
CH_CONTAINER=${CH_CONTAINER:-clickhouse-server-odbc}
DRY_RUN=${DRY_RUN:-0}

START="${YM}-01"
END=$(date -d "${START} +1 month" +%Y-%m-01)

# 五階條件與檔名：FACTORY / LINE 留空則該層不篩、檔名不帶
DIM_FILTER="region = '${REGION}' AND plant = '${PLANT}'"
TAG="${YM}_${REGION}_${PLANT}"
if [ -n "${FACTORY}" ]; then
  DIM_FILTER="${DIM_FILTER} AND factory = '${FACTORY}'"
  TAG="${TAG}_${FACTORY}"
fi
if [ -n "${LINE}" ]; then
  DIM_FILTER="${DIM_FILTER} AND line = '${LINE}'"
  TAG="${TAG}_${LINE}"
fi
S3_PATH="${S3_ENDPOINT}/${S3_BUCKET}/${S3_PREFIX}/${TAG}_{_partition_id}.csv.gz"

# 日期篩選：對齊 gold summary 的兩套語意（硬邊界 2026-04-01，同 backfill_gold_summary*.sql）
#   < 2026-04  : Day 粒度為事件日語意，需含「他月開單、本月簽收/完工」的跨月任務，
#                否則明細檔湊不出畫面數字（2026-03 CNE/WJ2 V1 為例，缺 26 筆）
#   >= 2026-04 : Day 粒度為開單日 cohort，維持只取本月開單
if [[ "${YM}" < "2026-04" ]]; then
  DATE_FILTER="( (task_start_date >= '${START}' AND task_start_date < '${END}')
              OR (task_claim_date >= '${START}' AND task_claim_date < '${END}')
              OR (task_end_date   >= '${START}' AND task_end_date   < '${END}') )"
else
  DATE_FILTER="task_start_date >= '${START}' AND task_start_date < '${END}'"
fi

WHERE="${DATE_FILTER}
  AND ${DIM_FILTER}
  AND is_excluded = 0"

# 本月開單 cohort 標記：週/月粒度對帳只能數這些列（跨月補進來的列標 0）
COHORT="if(task_start_date >= '${START}' AND task_start_date < '${END}', 1, 0)"

# 就地重算結算狀態（對齊 gold milestone；silver 存欄位在重建前仍有 1970 哨兵 bug）
EOM="toLastDayOfMonth(task_start_date)"
EOW="(toStartOfWeek(task_start_date, 3) + INTERVAL 6 DAY)"
STATUS_M="CASE WHEN task_end_date IS NOT NULL AND task_end_date <= ${EOM} THEN 'DONE'
               WHEN task_claim_date IS NOT NULL AND task_claim_date <= ${EOM} THEN 'DOING'
               ELSE 'TODO' END"
STATUS_W="CASE WHEN task_end_date IS NOT NULL AND task_end_date <= ${EOW} THEN 'DONE'
               WHEN task_claim_date IS NOT NULL AND task_claim_date <= ${EOW} THEN 'DOING'
               ELSE 'TODO' END"

echo "== 篩選: ${TAG}  (${START} ~ ${END})"
echo "== 目標: ${S3_PATH}"

# 對帳預覽（月結算，應等於 L5 Summary）— 只數本月開單 cohort，跨月補進來的列不計
docker exec -i "${CH_CONTAINER}" clickhouse-client --query "
  SELECT vx_type, count() AS total_task,
         countIf(sm='TODO') AS todo, countIf(sm='DOING') AS doing, countIf(sm='DONE') AS done
  FROM (SELECT vx_type, ${STATUS_M} AS sm FROM silver.mv_fact_task_vx FINAL
        WHERE ${WHERE} AND ${COHORT} = 1)
  GROUP BY vx_type ORDER BY vx_type FORMAT PrettyCompact"

if [ "${DRY_RUN}" = "1" ]; then
  echo "== DRY_RUN=1，只對帳不寫出。"; exit 0
fi

# 寫出 S3：去 5 個混淆欄 + 就地修正 status + 補 cohort 標記 → 37 欄
echo "== 寫出到 S3 ..."
docker exec -i "${CH_CONTAINER}" clickhouse-client --query "
  INSERT INTO FUNCTION s3('${S3_PATH}', '${S3_AK}', '${S3_SK}', 'CSVWithNames')
  PARTITION BY vx_type
  SELECT * EXCEPT (task_primary_date, task_create_date, ui_time_field, _mview_update_time, task_status)
           REPLACE (${STATUS_W} AS status_weekly, ${STATUS_M} AS status_monthly),
         ${COHORT} AS in_month_cohort
  FROM silver.mv_fact_task_vx FINAL
  WHERE ${WHERE}"

echo "== 完成: ${S3_PREFIX}/${TAG}_V1.csv.gz / _V2 / _V3"
