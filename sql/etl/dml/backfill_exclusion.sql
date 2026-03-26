-- Phase 3b: Update Exclusion Flags
ALTER TABLE silver.mv_fact_task_vx 
UPDATE is_excluded = 1, exclude_reason = 'autoComplete_flag'
WHERE task_id IN (
    SELECT TASK_ID_ FROM bronze.bpm_act_hi_varinst 
    WHERE NAME_ = 'autoComplete' AND LONG_ = 1
      AND TASK_ID_ IN (
          SELECT DISTINCT ID_ FROM bronze.bpm_act_hi_taskinst
          WHERE (START_TIME_ >= toDateTime64('{start_ts}', 3) AND START_TIME_ <= toDateTime64('{end_ts}', 3))
             OR (CLAIM_TIME_ >= toDateTime64('{start_ts}', 3) AND CLAIM_TIME_ <= toDateTime64('{end_ts}', 3))
             OR (END_TIME_ >= toDateTime64('{start_ts}', 3) AND END_TIME_ <= toDateTime64('{end_ts}', 3))
      )
)

