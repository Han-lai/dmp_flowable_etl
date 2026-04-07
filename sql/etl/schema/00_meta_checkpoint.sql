-- Create the ETL Checkpoint Metadata Table
-- Purpose: Track the progress of computation windows for fault-tolerant ETL.
-- Database: ops_metrics (運維監控，與 Bronze 原始資料分離)

CREATE TABLE IF NOT EXISTS ops_metrics.etl_checkpoint (
    phase          String,           -- 'silver_varinst_pivoted' or 'gold_task_completion'
    window_start   DateTime64(3),    -- 對應 execute_etl.py 寫入的 datetime string
    window_end     DateTime64(3),
    status         String,           -- 'SUCCESS', 'FAILED', 'RUNNING'
    error_msg      String DEFAULT '',
    duration_ms    Float64 DEFAULT 0,
    result_rows    UInt64 DEFAULT 0,
    result_bytes   UInt64 DEFAULT 0,
    update_time    DateTime64(3) DEFAULT now()
) ENGINE = ReplacingMergeTree(update_time)
ORDER BY (phase, window_start, window_end);
