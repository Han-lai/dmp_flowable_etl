-- 同步 ACT_RE_PROCDEF（流程定義）
-- 來源：APP_SRV_BPM

DROP TABLE IF EXISTS bronze.bpm_act_re_procdef;

CREATE TABLE bronze.bpm_act_re_procdef
ENGINE = MergeTree()
ORDER BY (KEY_, VERSION_, ID_)
AS SELECT * FROM jdbc('mssql_master', 'SELECT * FROM APP_SRV_BPM.dbo.ACT_RE_PROCDEF');

SELECT 'bpm_act_re_procdef' as table_name, count(*) as row_count FROM bronze.bpm_act_re_procdef;
