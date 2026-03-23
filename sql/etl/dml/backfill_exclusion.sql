-- Phase 3b: Update Exclusion Flags
ALTER TABLE silver.mv_fact_task_vx 
UPDATE is_excluded = 1, exclude_reason = 'autoComplete_flag'
WHERE task_id IN (
    SELECT TASK_ID_ FROM bronze.bpm_act_hi_varinst WHERE NAME_ = 'autoComplete' AND LONG_ = 1
)
