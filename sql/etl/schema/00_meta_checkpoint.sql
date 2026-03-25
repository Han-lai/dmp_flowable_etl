-- Create the ETL Checkpoint Metadata Table
-- Purpose: Track the progress of computation windows for fault-tolerant ETL.

CREATE TABLE IF NOT EXISTS bronze.etl_checkpoint (
    phase String,                    -- 'silver_varinst_pivoted' or 'gold_task_completion'
    window_start Date,
    window_end Date,
    status String,                   -- 'SUCCESS', 'FAILED', 'RUNNING'
    error_msg String DEFAULT '',
    update_time DateTime64(3) DEFAULT now()
) ENGINE = ReplacingMergeTree(update_time)
ORDER BY (phase, window_start, window_end);
