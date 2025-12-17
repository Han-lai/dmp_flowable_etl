-- 同步 ACT_HI_VARINST（流程變數歷史）
-- 來源：APP_SRV_BPM

DROP TABLE IF EXISTS bronze.bpm_act_hi_varinst;

CREATE TABLE bronze.bpm_act_hi_varinst
ENGINE = MergeTree()
ORDER BY (PROC_INST_ID_, NAME_, ID_)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_BPM.dbo.ACT_HI_VARINST');

SELECT 'bpm_act_hi_varinst' as table_name, count(*) as row_count FROM bronze.bpm_act_hi_varinst;
