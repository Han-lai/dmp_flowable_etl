#!/usr/bin/env python3
"""
MSSQL vs ClickHouse 資料不一致分析腳本
分析 2025-12-25 WJ2/NBU/E5 的資料差異
"""

import pyodbc
import clickhouse_connect
import pandas as pd
from datetime import datetime
import os
from typing import Dict, List, Tuple, Any

class DataInconsistencyAnalyzer:
    def __init__(self):
        # 分析條件
        self.analysis_date = '2025-12-25'
        self.plant = 'WJ2'
        self.factory = 'NBU'
        self.line = 'E5'
        
        # MSSQL 連接
        self.mssql_conn = self._connect_mssql()
        
        # ClickHouse 連接
        self.ch_client = clickhouse_connect.get_client(
            host='REDACTED_IP',
            port=8121,
            username='default',
            password='default'
        )
    
    def _connect_mssql(self):
        """建立 MSSQL 連接"""
        drivers = [
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 13 for SQL Server", 
            "SQL Server Native Client 11.0",
            "SQL Server"
        ]
        
        for driver in drivers:
            try:
                conn_str = (
                    f"DRIVER={{{driver}}};"
                    "SERVER=twtpesqldv2.delta.corp,1433;"
                    "DATABASE=APP_SRV_BPM;"
                    "UID=DMP_APP_SRV;"
                    "PWD=APP@DB#01;"
                )
                conn = pyodbc.connect(conn_str)
                print(f"✓ MSSQL 使用驅動程式: {driver}")
                return conn
            except Exception as e:
                print(f"✗ 驅動程式 {driver} 失敗: {e}")
                continue
        
        raise Exception("所有 MSSQL ODBC 驅動程式都無法連線")
        
        # 分析條件
        self.analysis_date = '2025-12-25'
        self.plant = 'WJ2'
        self.factory = 'NBU'
        self.line = 'E5'
        
    def get_mssql_reference_data(self) -> pd.DataFrame:
        """取得 MSSQL Reference SQL 的查詢結果"""
        
        reference_sql = """
        DECLARE @startDateTime DATETIME = '2025-12-25 00:00:00';
        DECLARE @endDateTime   DATETIME = '2025-12-25 23:59:59';

        SELECT
            hi.PROC_INST_ID_ as processInstanceId,
            pd.KEY_ as processDefinitionKey,
            pd.NAME_ as processDefinitionName,

            -- 流程变量
            var_plant.TEXT_ as plant,
            var_factory.TEXT_  as factory,
            var_productionArea.TEXT_ as productionArea,
            var_lineName.TEXT_ as line,
            var_modelName.TEXT_ as modelName,
            var_deliveryArea.TEXT_ as deliveryArea,
            var_scheduleNumber.TEXT_ as scheduleNumber,
            var_moNumber.TEXT_ as moNumber,
            var_sapPlant.TEXT_ as sapPlant,
            var_sapProductGroup.TEXT_ as sapProductGroup,
            var_pallet.TEXT_ as pallet,
            var_transferNo.TEXT_ as transferNo,
            var_qBlockEventId.TEXT_ as qBlockEventId,
            var_defectSn.TEXT_ as defectSn,
            CONCAT('_', var_time.TEXT_) as timeKey,

            hti.ID_ as taskId,
            hti.TASK_DEF_KEY_ as taskDefinitionKey,
            hti.NAME_ as taskName,
            CASE
                WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                ELSE 'TODO'
            END as taskStatus,
            CASE
                WHEN (
                    SELECT TOP 1 LONG_
                    FROM APP_SRV_BPM.dbo.ACT_HI_VARINST
                    WHERE TASK_ID_ = hti.ID_ AND NAME_ = 'autoComplete'
                ) = 1 THEN 'Y'
                ELSE 'N'
            END as taskBypass,

            hti.ASSIGNEE_ as taskAssignee,
            he.ADAccount as taskAssigneeAccount,
            he.EmpName as taskAssigneeName,
            CONVERT(VARCHAR, hti.START_TIME_, 120) as taskCreateTime,
            CONVERT(VARCHAR, hti.CLAIM_TIME_, 120) as taskClaimTime,
            CONVERT(VARCHAR, hti.END_TIME_, 120) as taskEndTime,

            CASE
                WHEN hti.END_TIME_ IS NOT NULL THEN
                    ROUND(CAST(DATEDIFF(SECOND, hti.START_TIME_, hti.END_TIME_) AS FLOAT) / 60, 2)
                ELSE
                    ROUND(CAST(DATEDIFF(SECOND, hti.START_TIME_, GETDATE()) AS FLOAT) / 60, 2)
            END as taskDurationMinutes,

            CASE
                WHEN hti.END_TIME_ IS NOT NULL THEN
                    ROUND(CAST(DATEDIFF(SECOND, hti.CLAIM_TIME_, hti.END_TIME_) AS FLOAT) / 60, 2)
                ELSE
                    ROUND(CAST(DATEDIFF(SECOND, hti.CLAIM_TIME_, GETDATE()) AS FLOAT) / 60, 2)
            END as taskWorkMinutes,

            hi.DELETE_REASON_ as deleteReason

        FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant on hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ and var_plant.NAME_ = 'plant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory on hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ and var_factory.NAME_ = 'factory'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_productionArea on hi.PROC_INST_ID_ = var_productionArea.PROC_INST_ID_ and var_productionArea.NAME_ = 'productionArea'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName on hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ and var_lineName.NAME_ = 'lineName'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_modelName on hi.PROC_INST_ID_ = var_modelName.PROC_INST_ID_ and var_modelName.NAME_ = 'modelName'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_deliveryArea on hi.PROC_INST_ID_ = var_deliveryArea.PROC_INST_ID_ and var_deliveryArea.NAME_ = 'deliveryArea'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_scheduleNumber on hi.PROC_INST_ID_ = var_scheduleNumber.PROC_INST_ID_ and var_scheduleNumber.NAME_ = 'scheduleNumber'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_moNumber on hi.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ and var_moNumber.NAME_ = 'moNumber'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_sapPlant on hi.PROC_INST_ID_ = var_sapPlant.PROC_INST_ID_ and var_sapPlant.NAME_ = 'sapPlant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_sapProductGroup on hi.PROC_INST_ID_ = var_sapProductGroup.PROC_INST_ID_ and var_sapProductGroup.NAME_ = 'sapProductGroup'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_pallet on hi.PROC_INST_ID_ = var_pallet.PROC_INST_ID_ and var_pallet.NAME_ = 'pallet'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_transferNo on hi.PROC_INST_ID_ = var_transferNo.PROC_INST_ID_ and var_transferNo.NAME_ = 'transferNo'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_qBlockEventId on hi.PROC_INST_ID_ = var_qBlockEventId.PROC_INST_ID_ and var_qBlockEventId.NAME_ = 'qBlockEventId'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_defectSn on hi.PROC_INST_ID_ = var_defectSn.PROC_INST_ID_ and var_defectSn.NAME_ = 'defectSn'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_time on hi.PROC_INST_ID_ = var_time.PROC_INST_ID_ and var_time.NAME_ = 'time'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_RE_PROCDEF pd ON hi.PROC_DEF_ID_ = pd.ID_
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
        LEFT JOIN APP_SRV_COMMON.dbo.HR_Employee he on hti.ASSIGNEE_ = he.EmpCode
        WHERE 1=1
        AND (
               hti.START_TIME_ BETWEEN @startDateTime AND @endDateTime
            OR hti.CLAIM_TIME_ BETWEEN @startDateTime AND @endDateTime
            OR hti.END_TIME_   BETWEEN @startDateTime AND @endDateTime
        )
        AND var_plant.TEXT_ = 'WJ2'
        AND var_factory.TEXT_ = 'NBU'
        AND var_lineName.TEXT_ = 'E5'
        ORDER BY hti.START_TIME_, hti.ID_
        """
        
        print("🔍 執行 MSSQL Reference Query...")
        df = pd.read_sql(reference_sql, self.mssql_conn)
        print(f"✅ MSSQL 查詢完成，共 {len(df)} 筆記錄")
        return df
    
    def get_clickhouse_bronze_data(self) -> pd.DataFrame:
        """取得 ClickHouse Bronze 層對應資料"""
        
        bronze_sql = """
        SELECT 
            p.PROC_INST_ID_ as processInstanceId,
            pd.KEY_ as processDefinitionKey,
            pd.NAME_ as processDefinitionName,
            
            -- 從 varinst 取得流程變數
            v_plant.TEXT_ as plant,
            v_factory.TEXT_ as factory,
            v_productionArea.TEXT_ as productionArea,
            v_lineName.TEXT_ as line,
            v_modelName.TEXT_ as modelName,
            v_deliveryArea.TEXT_ as deliveryArea,
            v_scheduleNumber.TEXT_ as scheduleNumber,
            v_moNumber.TEXT_ as moNumber,
            v_sapPlant.TEXT_ as sapPlant,
            v_sapProductGroup.TEXT_ as sapProductGroup,
            v_pallet.TEXT_ as pallet,
            v_transferNo.TEXT_ as transferNo,
            v_qBlockEventId.TEXT_ as qBlockEventId,
            v_defectSn.TEXT_ as defectSn,
            concat('_', v_time.TEXT_) as timeKey,
            
            t.ID_ as taskId,
            t.TASK_DEF_KEY_ as taskDefinitionKey,
            t.NAME_ as taskName,
            
            CASE
                WHEN t.END_TIME_ IS NOT NULL THEN 'DONE'
                WHEN t.ASSIGNEE_ IS NOT NULL AND t.ASSIGNEE_ != '' THEN 'DOING'
                ELSE 'TODO'
            END as taskStatus,
            
            CASE
                WHEN tb.LONG_ = 1 THEN 'Y'
                ELSE 'N'
            END as taskBypass,
            
            t.ASSIGNEE_ as taskAssignee,
            he.ADAccount as taskAssigneeAccount,
            he.EmpName as taskAssigneeName,
            toString(t.START_TIME_) as taskCreateTime,
            toString(t.CLAIM_TIME_) as taskClaimTime,
            toString(t.END_TIME_) as taskEndTime,
            
            CASE
                WHEN t.END_TIME_ IS NOT NULL THEN
                    round(dateDiff('second', t.START_TIME_, t.END_TIME_) / 60.0, 2)
                ELSE
                    round(dateDiff('second', t.START_TIME_, now()) / 60.0, 2)
            END as taskDurationMinutes,
            
            CASE
                WHEN t.END_TIME_ IS NOT NULL AND t.CLAIM_TIME_ IS NOT NULL THEN
                    round(dateDiff('second', t.CLAIM_TIME_, t.END_TIME_) / 60.0, 2)
                WHEN t.CLAIM_TIME_ IS NOT NULL THEN
                    round(dateDiff('second', t.CLAIM_TIME_, now()) / 60.0, 2)
                ELSE NULL
            END as taskWorkMinutes,
            
            p.DELETE_REASON_ as deleteReason
            
        FROM bronze.bpm_act_hi_procinst p
        LEFT JOIN bronze.bpm_act_hi_varinst v_plant 
            ON p.PROC_INST_ID_ = v_plant.PROC_INST_ID_ AND v_plant.NAME_ = 'plant'
        LEFT JOIN bronze.bpm_act_hi_varinst v_factory 
            ON p.PROC_INST_ID_ = v_factory.PROC_INST_ID_ AND v_factory.NAME_ = 'factory'
        LEFT JOIN bronze.bpm_act_hi_varinst v_productionArea 
            ON p.PROC_INST_ID_ = v_productionArea.PROC_INST_ID_ AND v_productionArea.NAME_ = 'productionArea'
        LEFT JOIN bronze.bpm_act_hi_varinst v_lineName 
            ON p.PROC_INST_ID_ = v_lineName.PROC_INST_ID_ AND v_lineName.NAME_ = 'lineName'
        LEFT JOIN bronze.bpm_act_hi_varinst v_modelName 
            ON p.PROC_INST_ID_ = v_modelName.PROC_INST_ID_ AND v_modelName.NAME_ = 'modelName'
        LEFT JOIN bronze.bpm_act_hi_varinst v_deliveryArea 
            ON p.PROC_INST_ID_ = v_deliveryArea.PROC_INST_ID_ AND v_deliveryArea.NAME_ = 'deliveryArea'
        LEFT JOIN bronze.bpm_act_hi_varinst v_scheduleNumber 
            ON p.PROC_INST_ID_ = v_scheduleNumber.PROC_INST_ID_ AND v_scheduleNumber.NAME_ = 'scheduleNumber'
        LEFT JOIN bronze.bpm_act_hi_varinst v_moNumber 
            ON p.PROC_INST_ID_ = v_moNumber.PROC_INST_ID_ AND v_moNumber.NAME_ = 'moNumber'
        LEFT JOIN bronze.bpm_act_hi_varinst v_sapPlant 
            ON p.PROC_INST_ID_ = v_sapPlant.PROC_INST_ID_ AND v_sapPlant.NAME_ = 'sapPlant'
        LEFT JOIN bronze.bpm_act_hi_varinst v_sapProductGroup 
            ON p.PROC_INST_ID_ = v_sapProductGroup.PROC_INST_ID_ AND v_sapProductGroup.NAME_ = 'sapProductGroup'
        LEFT JOIN bronze.bpm_act_hi_varinst v_pallet 
            ON p.PROC_INST_ID_ = v_pallet.PROC_INST_ID_ AND v_pallet.NAME_ = 'pallet'
        LEFT JOIN bronze.bpm_act_hi_varinst v_transferNo 
            ON p.PROC_INST_ID_ = v_transferNo.PROC_INST_ID_ AND v_transferNo.NAME_ = 'transferNo'
        LEFT JOIN bronze.bpm_act_hi_varinst v_qBlockEventId 
            ON p.PROC_INST_ID_ = v_qBlockEventId.PROC_INST_ID_ AND v_qBlockEventId.NAME_ = 'qBlockEventId'
        LEFT JOIN bronze.bpm_act_hi_varinst v_defectSn 
            ON p.PROC_INST_ID_ = v_defectSn.PROC_INST_ID_ AND v_defectSn.NAME_ = 'defectSn'
        LEFT JOIN bronze.bpm_act_hi_varinst v_time 
            ON p.PROC_INST_ID_ = v_time.PROC_INST_ID_ AND v_time.NAME_ = 'time'
        LEFT JOIN bronze.bpm_act_re_procdef pd 
            ON p.PROC_DEF_ID_ = pd.ID_
        LEFT JOIN bronze.bpm_act_hi_taskinst t 
            ON p.PROC_INST_ID_ = t.PROC_INST_ID_
        LEFT JOIN bronze.common_hr_employee he 
            ON t.ASSIGNEE_ = he.EmpCode
        LEFT JOIN bronze.bpm_act_hi_varinst tb 
            ON t.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'
        WHERE 1=1
        AND (
               t.START_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59'
            OR t.CLAIM_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59'
            OR t.END_TIME_ BETWEEN '2025-12-25 00:00:00' AND '2025-12-25 23:59:59'
        )
        AND v_plant.TEXT_ = 'WJ2'
        AND v_factory.TEXT_ = 'NBU'
        AND v_lineName.TEXT_ = 'E5'
        ORDER BY t.START_TIME_, t.ID_
        """
        
        print("🔍 執行 ClickHouse Bronze Query...")
        df = self.ch_client.query_df(bronze_sql)
        print(f"✅ ClickHouse Bronze 查詢完成，共 {len(df)} 筆記錄")
        return df
    
    def get_clickhouse_silver_data(self) -> pd.DataFrame:
        """取得 ClickHouse Silver 層 MVIEW 資料"""
        
        silver_sql = """
        SELECT 
            task_id as taskId,
            proc_inst_id as processInstanceId,
            task_definition_key as taskDefinitionKey,
            task_name as taskName,
            task_status as taskStatus,
            task_bypass as taskBypass,
            task_assignee_account as taskAssignee,
            task_assignee_name as taskAssigneeName,
            toString(task_create_time) as taskCreateTime,
            toString(task_claim_time) as taskClaimTime,
            toString(task_end_time) as taskEndTime,
            
            CASE
                WHEN task_end_time IS NOT NULL THEN
                    round(dateDiff('second', task_create_time, task_end_time) / 60.0, 2)
                ELSE
                    round(dateDiff('second', task_create_time, now()) / 60.0, 2)
            END as taskDurationMinutes,
            
            CASE
                WHEN task_end_time IS NOT NULL AND task_claim_time IS NOT NULL THEN
                    round(dateDiff('second', task_claim_time, task_end_time) / 60.0, 2)
                WHEN task_claim_time IS NOT NULL THEN
                    round(dateDiff('second', task_claim_time, now()) / 60.0, 2)
                ELSE NULL
            END as taskWorkMinutes,
            
            plant,
            factory,
            line,
            mo_number as moNumber,
            vx_type,
            vx_subtype,
            is_excluded,
            exclude_reason
            
        FROM silver.mv_fact_task_vx_attribution FINAL
        WHERE toDate(task_create_time) = '2025-12-25'
        AND plant = 'WJ2'
        AND factory = 'NBU'
        AND line = 'E5'
        ORDER BY task_create_time, task_id
        """
        
        print("🔍 執行 ClickHouse Silver MVIEW Query...")
        df = self.ch_client.query_df(silver_sql)
        print(f"✅ ClickHouse Silver 查詢完成，共 {len(df)} 筆記錄")
        return df
    
    def get_clickhouse_gold_data(self) -> pd.DataFrame:
        """取得 ClickHouse Gold 層 MVIEW 資料"""
        
        gold_sql = """
        SELECT 
            snapshot_date,
            plant_code as plant,
            factory_code as factory,
            line_code as line,
            vx_type,
            vx_subtype,
            sum_total_task_qty as total_tasks,
            sum_todo_qty as todo_tasks,
            sum_doing_qty as doing_tasks,
            sum_done_qty as done_tasks,
            completion_rate,
            progress_rate,
            dimension_source,
            sum_mdm_primary_qty,
            sum_flowable_fallback_qty,
            sum_no_dimension_qty
            
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL
        WHERE snapshot_date = '2025-12-25'
        AND plant_code = 'WJ2'
        AND factory_code = 'NBU'
        AND line_code = 'E5'
        ORDER BY vx_type, vx_subtype
        """
        
        print("🔍 執行 ClickHouse Gold MVIEW Query...")
        df = self.ch_client.query_df(gold_sql)
        print(f"✅ ClickHouse Gold 查詢完成，共 {len(df)} 筆記錄")
        return df
    
    def compare_data_layers(self, mssql_df: pd.DataFrame, bronze_df: pd.DataFrame, 
                           silver_df: pd.DataFrame, gold_df: pd.DataFrame) -> Dict[str, Any]:
        """比較各層資料差異"""
        
        analysis = {
            'record_counts': {
                'mssql_reference': len(mssql_df),
                'clickhouse_bronze': len(bronze_df),
                'clickhouse_silver': len(silver_df),
                'gold_aggregated_rows': len(gold_df)
            },
            'data_loss_analysis': {},
            'field_mapping_issues': {},
            'transformation_issues': {}
        }
        
        # 1. 記錄數量分析
        print("\n📊 記錄數量分析:")
        print(f"MSSQL Reference: {len(mssql_df)} 筆")
        print(f"ClickHouse Bronze: {len(bronze_df)} 筆")
        print(f"ClickHouse Silver: {len(silver_df)} 筆")
        print(f"ClickHouse Gold: {len(gold_df)} 筆 (聚合後)")
        
        # 2. Bronze 層比對
        if len(mssql_df) != len(bronze_df):
            print(f"\n⚠️  Bronze 層資料遺失: MSSQL {len(mssql_df)} vs Bronze {len(bronze_df)}")
            analysis['data_loss_analysis']['bronze_layer'] = {
                'expected': len(mssql_df),
                'actual': len(bronze_df),
                'missing': len(mssql_df) - len(bronze_df)
            }
        
        # 3. Silver 層比對
        if len(bronze_df) != len(silver_df):
            print(f"\n⚠️  Silver 層資料遺失: Bronze {len(bronze_df)} vs Silver {len(silver_df)}")
            analysis['data_loss_analysis']['silver_layer'] = {
                'expected': len(bronze_df),
                'actual': len(silver_df),
                'missing': len(bronze_df) - len(silver_df)
            }
        
        # 4. 欄位值比對 (以 taskId 為 key)
        if len(mssql_df) > 0 and len(bronze_df) > 0:
            # 找出共同的 taskId
            mssql_tasks = set(mssql_df['taskId'].astype(str))
            bronze_tasks = set(bronze_df['taskId'].astype(str))
            common_tasks = mssql_tasks.intersection(bronze_tasks)
            
            print(f"\n🔍 共同任務 ID: {len(common_tasks)} 個")
            print(f"MSSQL 獨有: {len(mssql_tasks - bronze_tasks)} 個")
            print(f"Bronze 獨有: {len(bronze_tasks - mssql_tasks)} 個")
            
            if len(common_tasks) > 0:
                # 比對欄位值
                sample_task = list(common_tasks)[0]
                mssql_row = mssql_df[mssql_df['taskId'].astype(str) == sample_task].iloc[0]
                bronze_row = bronze_df[bronze_df['taskId'].astype(str) == sample_task].iloc[0]
                
                print(f"\n📋 樣本任務 {sample_task} 欄位比對:")
                field_diffs = {}
                for col in mssql_df.columns:
                    if col in bronze_df.columns:
                        mssql_val = str(mssql_row[col]) if pd.notna(mssql_row[col]) else 'NULL'
                        bronze_val = str(bronze_row[col]) if pd.notna(bronze_row[col]) else 'NULL'
                        if mssql_val != bronze_val:
                            field_diffs[col] = {
                                'mssql': mssql_val,
                                'bronze': bronze_val
                            }
                            print(f"  {col}: MSSQL='{mssql_val}' vs Bronze='{bronze_val}'")
                
                analysis['field_mapping_issues'] = field_diffs
        
        return analysis
    
    def create_clickhouse_validation_table(self, mssql_df: pd.DataFrame):
        """建立 ClickHouse 驗證用表格，Schema 與 MSSQL 查詢結果一致"""
        
        print("🏗️  建立 ClickHouse 驗證表格...")
        self.ch_client.command("CREATE DATABASE IF NOT EXISTS validation")
        
        # 分別執行 DROP 和 CREATE
        drop_sql = "DROP TABLE IF EXISTS validation.mssql_reference_l5_tasks"
        self.ch_client.command(drop_sql)
        
        create_table_sql = """
        CREATE TABLE validation.mssql_reference_l5_tasks
        (
            processInstanceId String,
            processDefinitionKey Nullable(String),
            processDefinitionName Nullable(String),
            plant Nullable(String),
            factory Nullable(String),
            productionArea Nullable(String),
            line Nullable(String),
            modelName Nullable(String),
            deliveryArea Nullable(String),
            scheduleNumber Nullable(String),
            moNumber Nullable(String),
            sapPlant Nullable(String),
            sapProductGroup Nullable(String),
            pallet Nullable(String),
            transferNo Nullable(String),
            qBlockEventId Nullable(String),
            defectSn Nullable(String),
            timeKey Nullable(String),
            taskId String,
            taskDefinitionKey Nullable(String),
            taskName Nullable(String),
            taskStatus Nullable(String),
            taskBypass Nullable(String),
            taskAssignee Nullable(String),
            taskAssigneeAccount Nullable(String),
            taskAssigneeName Nullable(String),
            taskCreateTime Nullable(String),
            taskClaimTime Nullable(String),
            taskEndTime Nullable(String),
            taskDurationMinutes Nullable(Float64),
            taskWorkMinutes Nullable(Float64),
            deleteReason Nullable(String),
            _import_time DateTime64(3) DEFAULT now64(3)
        )
        ENGINE = MergeTree()
        ORDER BY (taskId)
        """
        
        self.ch_client.command(create_table_sql)
        
        # 插入 MSSQL 資料
        if len(mssql_df) > 0:
            # 處理 NULL 值
            mssql_df_clean = mssql_df.copy()
            for col in mssql_df_clean.columns:
                mssql_df_clean[col] = mssql_df_clean[col].astype(str)
                mssql_df_clean[col] = mssql_df_clean[col].replace('nan', '')
                mssql_df_clean[col] = mssql_df_clean[col].replace('None', '')
            
            self.ch_client.insert_df('validation.mssql_reference_l5_tasks', mssql_df_clean)
            print(f"✅ 已插入 {len(mssql_df)} 筆 MSSQL 參考資料")
        
        return create_table_sql
    
    def generate_field_mapping_table(self) -> str:
        """產生 MSSQL → ClickHouse 欄位對應表"""
        
        mapping_table = """
        # MSSQL → ClickHouse 欄位對應表
        
        | MSSQL 欄位 | ClickHouse Bronze | ClickHouse Silver | ClickHouse Gold | 資料型別 | 轉換邏輯 |
        |------------|-------------------|-------------------|-----------------|----------|----------|
        | processInstanceId | PROC_INST_ID_ | proc_inst_id | - | String | 直接對應 |
        | processDefinitionKey | KEY_ (from procdef) | - | - | String | JOIN 取得 |
        | processDefinitionName | NAME_ (from procdef) | - | - | String | JOIN 取得 |
        | plant | TEXT_ (varinst plant) | plant | plant_code | String | EAV 轉置 |
        | factory | TEXT_ (varinst factory) | factory | factory_code | String | EAV 轉置 |
        | productionArea | TEXT_ (varinst productionArea) | - | - | String | EAV 轉置 |
        | line | TEXT_ (varinst lineName) | line | line_code | String | EAV 轉置 |
        | modelName | TEXT_ (varinst modelName) | - | - | String | EAV 轉置 |
        | deliveryArea | TEXT_ (varinst deliveryArea) | - | - | String | EAV 轉置 |
        | scheduleNumber | TEXT_ (varinst scheduleNumber) | - | - | String | EAV 轉置 |
        | moNumber | TEXT_ (varinst moNumber) | mo_number | - | String | EAV 轉置 |
        | sapPlant | TEXT_ (varinst sapPlant) | - | - | String | EAV 轉置 |
        | sapProductGroup | TEXT_ (varinst sapProductGroup) | - | - | String | EAV 轉置 |
        | pallet | TEXT_ (varinst pallet) | - | - | String | EAV 轉置 |
        | transferNo | TEXT_ (varinst transferNo) | - | - | String | EAV 轉置 |
        | qBlockEventId | TEXT_ (varinst qBlockEventId) | - | - | String | EAV 轉置 |
        | defectSn | TEXT_ (varinst defectSn) | - | - | String | EAV 轉置 |
        | timeKey | CONCAT('_', TEXT_) | - | - | String | EAV 轉置 + 前綴 |
        | taskId | ID_ | task_id | - | String | 直接對應 |
        | taskDefinitionKey | TASK_DEF_KEY_ | task_definition_key | - | String | 直接對應 |
        | taskName | NAME_ | task_name | - | String | 直接對應 |
        | taskStatus | CASE WHEN... | task_status | - | String | 狀態邏輯轉換 |
        | taskBypass | CASE WHEN LONG_=1 | task_bypass | - | String | autoComplete 變數 |
        | taskAssignee | ASSIGNEE_ | task_assignee_account | - | String | 直接對應 |
        | taskAssigneeAccount | ADAccount (HR_Employee) | - | - | String | JOIN 取得 |
        | taskAssigneeName | EmpName (HR_Employee) | task_assignee_name | - | String | JOIN 取得 |
        | taskCreateTime | START_TIME_ | task_create_time | snapshot_date | DateTime/String | 格式轉換 |
        | taskClaimTime | CLAIM_TIME_ | task_claim_time | - | DateTime/String | 格式轉換 |
        | taskEndTime | END_TIME_ | task_end_time | - | DateTime/String | 格式轉換 |
        | taskDurationMinutes | DATEDIFF 計算 | 計算欄位 | - | Float64 | 時間差計算 |
        | taskWorkMinutes | DATEDIFF 計算 | 計算欄位 | - | Float64 | 時間差計算 |
        | deleteReason | DELETE_REASON_ | - | - | String | 直接對應 |
        | - | - | vx_type | vx_type | String | 業務邏輯計算 |
        | - | - | vx_subtype | vx_subtype | String | 業務邏輯計算 |
        | - | - | is_excluded | - | Int | 排除邏輯 |
        | - | - | exclude_reason | - | String | 排除原因 |
        """
        
        return mapping_table
    
    def generate_analysis_report(self, analysis: Dict[str, Any]) -> str:
        """產生分析報告"""
        
        report = f"""
        # MSSQL vs ClickHouse 資料不一致分析報告
        
        ## 分析條件
        - 日期: {self.analysis_date}
        - 條件: plant='{self.plant}', factory='{self.factory}', line='{self.line}'
        - 分析時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        ## 1. 記錄數量統計
        
        | 資料層 | 記錄數 | 說明 |
        |--------|--------|------|
        | MSSQL Reference | {analysis['record_counts']['mssql_reference']} | 正確基準 |
        | ClickHouse Bronze | {analysis['record_counts']['clickhouse_bronze']} | 原始同步層 |
        | ClickHouse Silver | {analysis['record_counts']['clickhouse_silver']} | 轉換邏輯層 |
        | ClickHouse Gold | {analysis['record_counts']['gold_aggregated_rows']} | 聚合指標層 |
        
        ## 2. 資料遺失分析
        
        """
        
        if analysis['data_loss_analysis']:
            for layer, loss_info in analysis['data_loss_analysis'].items():
                report += f"""
        ### {layer.upper()} 層資料遺失
        - 預期記錄數: {loss_info['expected']}
        - 實際記錄數: {loss_info['actual']}
        - 遺失記錄數: {loss_info['missing']}
        - 遺失比例: {(loss_info['missing']/loss_info['expected']*100):.2f}%
        """
        else:
            report += "\n✅ 未發現資料遺失問題\n"
        
        report += """
        ## 3. 欄位對應問題
        
        """
        
        if analysis['field_mapping_issues']:
            report += "發現以下欄位值不一致:\n\n"
            for field, diff in analysis['field_mapping_issues'].items():
                report += f"- **{field}**: MSSQL='{diff['mssql']}' vs ClickHouse='{diff['bronze']}'\n"
        else:
            report += "✅ 樣本檢查未發現欄位對應問題\n"
        
        report += """
        ## 4. 可能原因分析
        
        ### Bronze 層問題
        1. **同步時間差**: MSSQL 與 ClickHouse 同步可能有時間延遲
        2. **資料過濾條件**: Bronze 層的 WHERE 條件可能與 MSSQL 不一致
        3. **JOIN 邏輯差異**: 多表 JOIN 的邏輯可能不完全相同
        4. **資料型別轉換**: DateTime 格式轉換可能造成過濾條件失效
        
        ### Silver 層問題
        1. **EAV 轉置邏輯**: ACT_HI_VARINST 的 EAV 轉置可能遺漏資料
        2. **MVIEW 更新延遲**: Materialized View 可能未即時更新
        3. **業務邏輯錯誤**: Vx 歸屬、排除邏輯可能與需求不符
        4. **NULL 值處理**: NULL 值的處理邏輯可能不一致
        
        ### Gold 層問題
        1. **聚合邏輯錯誤**: 聚合條件可能過於嚴格
        2. **維度對應問題**: MDM 維度對應可能遺漏資料
        3. **時間分組問題**: 日期分組邏輯可能不正確
        
        ## 5. 建議修正方案
        
        ### 立即修正
        1. **檢查同步狀態**: 確認 Bronze 層資料是否完整同步
        2. **驗證過濾條件**: 比對 MSSQL 與 ClickHouse 的 WHERE 條件
        3. **檢查 MVIEW 狀態**: 確認 Silver 層 MVIEW 是否正常更新
        
        ### 中期改善
        1. **統一時間處理**: 標準化所有層的 DateTime 處理邏輯
        2. **完善 NULL 處理**: 統一 NULL 值的處理方式
        3. **增加資料驗證**: 在每層轉換後增加資料完整性檢查
        
        ### 長期優化
        1. **建立監控機制**: 自動監控各層資料一致性
        2. **完善測試覆蓋**: 增加端到端的資料驗證測試
        3. **文檔化轉換邏輯**: 詳細記錄每層的轉換邏輯和業務規則
        """
        
        return report
    
    def run_analysis(self):
        """執行完整分析"""
        
        print("🚀 開始 MSSQL vs ClickHouse 資料不一致分析")
        print(f"📅 分析條件: {self.analysis_date}, {self.plant}/{self.factory}/{self.line}")
        
        try:
            # 1. 取得各層資料
            mssql_df = self.get_mssql_reference_data()
            bronze_df = self.get_clickhouse_bronze_data()
            silver_df = self.get_clickhouse_silver_data()
            gold_df = self.get_clickhouse_gold_data()
            
            # 2. 比較分析
            analysis = self.compare_data_layers(mssql_df, bronze_df, silver_df, gold_df)
            
            # 3. 建立驗證表格
            create_table_sql = self.create_clickhouse_validation_table(mssql_df)
            
            # 4. 產生報告
            report = self.generate_analysis_report(analysis)
            field_mapping = self.generate_field_mapping_table()
            
            # 5. 儲存結果
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            with open(f'logs/data_inconsistency_analysis_{timestamp}.md', 'w', encoding='utf-8') as f:
                f.write(report)
                f.write("\n\n")
                f.write(field_mapping)
            
            with open(f'sql/create_validation_table_{timestamp}.sql', 'w', encoding='utf-8') as f:
                f.write(create_table_sql)
            
            print(f"\n✅ 分析完成!")
            print(f"📄 報告已儲存: logs/data_inconsistency_analysis_{timestamp}.md")
            print(f"🗃️  驗證表格已建立: validation.mssql_reference_l5_tasks")
            print(f"📜 建表 SQL 已儲存: sql/create_validation_table_{timestamp}.sql")
            
            # 6. 顯示摘要
            print(f"\n📊 分析摘要:")
            print(f"MSSQL Reference: {len(mssql_df)} 筆")
            print(f"ClickHouse Bronze: {len(bronze_df)} 筆")
            print(f"ClickHouse Silver: {len(silver_df)} 筆")
            print(f"ClickHouse Gold: {len(gold_df)} 筆聚合")
            
            if len(mssql_df) != len(bronze_df):
                print(f"⚠️  Bronze 層遺失 {len(mssql_df) - len(bronze_df)} 筆資料")
            if len(bronze_df) != len(silver_df):
                print(f"⚠️  Silver 層遺失 {len(bronze_df) - len(silver_df)} 筆資料")
            
        except Exception as e:
            print(f"❌ 分析過程發生錯誤: {str(e)}")
            raise
        finally:
            # 關閉連接
            if hasattr(self, 'mssql_conn'):
                self.mssql_conn.close()
            if hasattr(self, 'ch_client'):
                self.ch_client.close()

if __name__ == "__main__":
    analyzer = DataInconsistencyAnalyzer()
    analyzer.run_analysis()