#!/usr/bin/env bash
# 依五階+月份篩選 L5 明細，依 vx_type 切檔壓縮寫出 .csv.gz 到 S3（CH server 端執行）。
# 用法: S3_AK=.. S3_SK=.. YM=2026-04 REGION=CNE PLANT=WJ2 FACTORY=NBU LINE=E5 ./export_l5_to_s3.sh
# 可選: S3_ENDPOINT / S3_BUCKET / S3_PREFIX / CH_CONTAINER / DRY_RUN=1
set -euo pipefail

YM=${YM:?例 2026-04}
REGION=${REGION:?例 CNE}
PLANT=${PLANT:?例 WJ2}
FACTORY=${FACTORY:?例 NBU}
LINE=${LINE:?例 E5}
S3_AK=${S3_AK:?}
S3_SK=${S3_SK:?}

S3_ENDPOINT=${S3_ENDPOINT:-http://cnwjns3.delta.corp}
S3_BUCKET=${S3_BUCKET:-dmp-lakehoused}
S3_PREFIX=${S3_PREFIX:-DMP_KPI}
CH_CONTAINER=${CH_CONTAINER:-clickhouse-server-odbc}
DRY_RUN=${DRY_RUN:-0}

START="${YM}-01"
END=$(date -d "${START} +1 month" +%Y-%m-01)
TAG="${YM}_${REGION}_${PLANT}_${FACTORY}_${LINE}"
S3_PATH="${S3_ENDPOINT}/${S3_BUCKET}/${S3_PREFIX}/${TAG}_{_partition_id}.csv.gz"

WHERE="task_start_date >= '${START}' AND task_start_date < '${END}'
  AND region = '${REGION}' AND plant = '${PLANT}'
  AND factory = '${FACTORY}' AND line = '${LINE}'
  AND is_excluded = 0"

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

# 對帳預覽（月結算，應等於 L5 Summary）
docker exec -i "${CH_CONTAINER}" clickhouse-client --query "
  SELECT vx_type, count() AS total_task,
         countIf(sm='TODO') AS todo, countIf(sm='DOING') AS doing, countIf(sm='DONE') AS done
  FROM (SELECT vx_type, ${STATUS_M} AS sm FROM silver.mv_fact_task_vx FINAL WHERE ${WHERE})
  GROUP BY vx_type ORDER BY vx_type FORMAT PrettyCompact"

if [ "${DRY_RUN}" = "1" ]; then
  echo "== DRY_RUN=1，只對帳不寫出。"; exit 0
fi

# 寫出 S3：去 5 個混淆欄 + 就地修正 status → 36 欄
echo "== 寫出到 S3 ..."
docker exec -i "${CH_CONTAINER}" clickhouse-client --query "
  INSERT INTO FUNCTION s3('${S3_PATH}', '${S3_AK}', '${S3_SK}', 'CSVWithNames')
  PARTITION BY vx_type
  SELECT * EXCEPT (task_primary_date, task_create_date, ui_time_field, _mview_update_time, task_status)
           REPLACE (${STATUS_W} AS status_weekly, ${STATUS_M} AS status_monthly)
  FROM silver.mv_fact_task_vx FINAL
  WHERE ${WHERE}"

echo "== 完成: ${S3_PREFIX}/${TAG}_V1.csv.gz / _V2 / _V3"
