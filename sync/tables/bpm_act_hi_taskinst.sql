-- 同步 ACT_HI_TASKINST（任務實例歷史）
-- 來源：APP_SRV_BPM

DROP TABLE IF EXISTS bronze.bpm_act_hi_taskinst;

CREATE TABLE bronze.bpm_act_hi_taskinst
ENGINE = MergeTree()
ORDER BY (PROC_INST_ID_, START_TIME_, ID_)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST');

SELECT 'bpm_act_hi_taskinst' as table_name, count(*) as row_count FROM bronze.bpm_act_hi_taskinst;
