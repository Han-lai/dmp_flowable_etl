-- 同步 ACT_HI_IDENTITYLINK（任務參與者歷史）
-- 來源：APP_SRV_BPM

DROP TABLE IF EXISTS bronze.bpm_act_hi_identitylink;

CREATE TABLE bronze.bpm_act_hi_identitylink
ENGINE = MergeTree()
ORDER BY (PROC_INST_ID_, TASK_ID_, ID_)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK');

SELECT 'bpm_act_hi_identitylink' as table_name, count(*) as row_count FROM bronze.bpm_act_hi_identitylink;
