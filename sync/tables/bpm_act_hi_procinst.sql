-- 同步 ACT_HI_PROCINST（流程實例歷史）
-- 來源：APP_SRV_BPM

DROP TABLE IF EXISTS bronze.bpm_act_hi_procinst;

CREATE TABLE bronze.bpm_act_hi_procinst
ENGINE = MergeTree()
ORDER BY (PROC_DEF_ID_, START_TIME_, ID_)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST');

SELECT 'bpm_act_hi_procinst' as table_name, count(*) as row_count FROM bronze.bpm_act_hi_procinst;
