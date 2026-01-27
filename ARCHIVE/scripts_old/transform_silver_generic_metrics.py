#!/usr/bin/env python3
"""
========================================
Silver 層轉換腳本 - 通用指標
========================================
轉換 Bronze 層資料到 Silver 層，支撐：
1. L5 任務執行完成率
2. 人員使用率

來源表：
- bronze.common_flowable_task_stats
- bronze.bpm_act_hi_procinst
- bronze.bpm_act_hi_varinst (轉置取得 moNumber)
- bronze.common_emp_node_role_mapping
- bronze.common_emp_org_info_mapping
- bronze.common_emp_user_group_mapping
- bronze.common_user_group
- bronze.common_hr_employee

目標表：
- silver.FACT_TASK_VX_ATTRIBUTION
- silver.DIM_CONFIG_USER

使用方式：
- python scripts/transform_silver_generic_metrics.py          # 全量轉換
- python scripts/transform_silver_generic_metrics.py --table task  # 只轉換任務表
- python scripts/transform_silver_generic_metrics.py --table user  # 只轉換用戶表

排程：
- 每日 Bronze 同步後執行
- 建議在 create_gold_snapshot.py 之前執行

變更紀錄：
- 2026-01-16: 改用 varinst.moNumber 判斷 V1 特殊規則（取代 FlowableTaskStats.MoNumber）
"""

import clickhouse_connect
from datetime import datetime
import logging
import argparse

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ClickHouse 連線設定
CH_CONFIG = {
    'host': '10.136.218.207',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}


def get_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(**CH_CONFIG)


# ============================================
# 表 1: FACT_TASK_VX_ATTRIBUTION 轉換
# ============================================
# 變更說明 (2026-01-16):
# - 改用 varinst.moNumber 判斷 V1 特殊規則
# - 原因：FlowableTaskStats.MoNumber 與 varinst.moNumber 內容不同
#   - FlowableTaskStats.MoNumber 可能為空或不完整
#   - varinst.moNumber 是流程變數中的實際工單編號
#   - 分析結果：用 varinst.moNumber 可找到 5,368 個額外的 V1 流程
# ============================================

TRANSFORM_FACT_TASK_VX_SQL = """
INSERT INTO silver.FACT_TASK_VX_ATTRIBUTION
WITH 
-- 從 varinst 轉置取得 moNumber 和維度資訊（EAV 結構轉置）
varinst_pivoted AS (
    SELECT 
        PROC_INST_ID_,
        MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS varinst_moNumber,
        MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS varinst_plant,
        MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS varinst_factory,
        MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS varinst_lineName
    FROM bronze.bpm_act_hi_varinst
    WHERE NAME_ IN ('moNumber', 'plant', 'factory', 'lineName')
    GROUP BY PROC_INST_ID_
)
SELECT
    -- 主鍵
    t.TaskId AS task_id,
    
    -- 時間維度
    COALESCE(t.TaskCreateDate, toDate('1970-01-01')) AS task_create_date,
    t.TaskEndDate AS task_end_date,
    t.TaskCreateTime AS task_create_time,
    t.TaskClaimTime AS task_claim_time,
    t.TaskEndTime AS task_end_time,
    
    -- 任務屬性
    COALESCE(t.TaskStatus, 'Unknown') AS task_status,
    COALESCE(t.TaskBypass, 'N') AS task_bypass,
    t.TaskDefinitionKey AS task_definition_key,
    t.TaskName AS task_name,
    
    -- 人員資訊
    t.TaskAssigneeName AS task_assignee_name,
    t.TaskAssigneeAccount AS task_assignee_account,
    
    -- 預計算：Vx 歸屬（修正後的邏輯：工單號規則優先級最高，無論 TaskDefinitionKey 是什麼）
    CASE 
        -- 優先級 1：工單號規則（最高，覆蓋所有 TaskDefinitionKey）
        WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%'
        THEN 'V1'
        
        -- 優先級 2：TaskDefinitionKey 前綴（當工單號規則不符合時）
        WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 'V1'
        WHEN t.TaskDefinitionKey LIKE 'V2%' THEN 'V2'
        WHEN t.TaskDefinitionKey LIKE 'V3%' THEN 'V3'
        
        -- 預設值
        ELSE COALESCE(substring(t.TaskDefinitionKey, 1, 2), 'Unknown')
    END AS vx_type,
    
    -- 預計算：V1 子類型（修正後的邏輯：工單號規則優先）
    CASE 
        -- 工單號規則的 V1 任務（無論原始 TaskDefinitionKey 是什麼）
        WHEN (COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%')
             AND p.BUSINESS_KEY_ LIKE '%NPE%'
        THEN 'V1_NPE'
        
        WHEN (COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
              OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%')
        THEN 'V1_MFG'
        
        -- TaskDefinitionKey 的 V1 任務（工單號規則不符合時）
        WHEN t.TaskDefinitionKey LIKE 'V1%' AND p.BUSINESS_KEY_ LIKE '%NPE%'
        THEN 'V1_NPE'
        
        WHEN t.TaskDefinitionKey LIKE 'V1%'
        THEN 'V1_MFG'
        
        -- 其他情況（V2/V3 等）
        ELSE NULL
    END AS vx_subtype,
    
    -- 是否套用特殊 V1 規則（修正後的邏輯：工單號規則優先）
    CASE 
        WHEN t.TaskDefinitionKey LIKE 'V1%' THEN 1
        -- 工單號規則（包含 315%）
        WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '196%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '199%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '200%'
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '210%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '212%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '213%'
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE '315%'
        THEN 1
        ELSE 0
    END AS is_special_v1_rule,
    
    -- 排除標記（Q/R 工單判斷仍使用 varinst_moNumber）
    CASE 
        WHEN t.TaskBypass != 'N' THEN 1
        WHEN t.TaskDefinitionKey LIKE 'E%' OR t.TaskDefinitionKey LIKE 'C%' THEN 1
        WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'Q%' 
             OR COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'R%' THEN 1
        ELSE 0
    END AS is_excluded,
    
    -- 排除原因
    CASE 
        WHEN t.TaskBypass != 'N' THEN 'bypass'
        WHEN t.TaskDefinitionKey LIKE 'E%' THEN 'E_prefix'
        WHEN t.TaskDefinitionKey LIKE 'C%' THEN 'C_prefix'
        WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'Q%' THEN 'Q_order'
        WHEN COALESCE(v.varinst_moNumber, t.MoNumber) LIKE 'R%' THEN 'R_order'
        ELSE NULL
    END AS exclude_reason,
    
    -- 維度（優先使用 varinst，Flowable 作為 fallback）
    COALESCE(v.varinst_plant, t.Plant) AS plant,
    COALESCE(v.varinst_factory, t.Factory) AS factory,
    COALESCE(v.varinst_lineName, t.Line) AS line,
    
    -- 關聯欄位
    t.ProcessInstanceId AS proc_inst_id,
    p.BUSINESS_KEY_ AS business_key,
    COALESCE(v.varinst_moNumber, t.MoNumber) AS mo_number,  -- 優先使用 varinst_moNumber
    p.NAME_ AS proc_name,
    
    -- Metadata
    now64(3) AS _transform_time

FROM bronze.common_flowable_task_stats t
LEFT JOIN bronze.bpm_act_hi_procinst p 
    ON t.ProcessInstanceId = p.PROC_INST_ID_
LEFT JOIN varinst_pivoted v
    ON t.ProcessInstanceId = v.PROC_INST_ID_
WHERE t.TaskId IS NOT NULL 
  AND t.TaskId != ''
"""


# ============================================
# 表 2: DIM_CONFIG_USER 轉換
# ============================================

TRANSFORM_DIM_CONFIG_USER_SQL = """
INSERT INTO silver.DIM_CONFIG_USER
WITH 
-- Step 1: 取得每個員工的所有 UserGroup
emp_groups AS (
    SELECT 
        eug.EmpCode,
        groupArray(ug.UserGroupName) AS user_group_names
    FROM bronze.common_emp_user_group_mapping eug
    INNER JOIN bronze.common_user_group ug 
        ON eug.UserGroupId = ug.UserGroupId
    GROUP BY eug.EmpCode
),

-- Step 2: 取得每個員工的 NodeCodes (格式: V1_3, V2_4 等)
emp_nodes AS (
    SELECT 
        EmpCode,
        groupArray(NodeCode) AS node_codes
    FROM bronze.common_emp_node_role_mapping
    GROUP BY EmpCode
),

-- Step 3: 取得每個員工的 Plant/Factory
emp_org AS (
    SELECT 
        eoi.EmpCode,
        eoi.Plant,
        COALESCE(mpm.MFG_PLANT_CODE, eoi.MFGFactoryId) AS factory
    FROM bronze.common_emp_org_info_mapping eoi
    LEFT JOIN bronze.common_mdm_mfg_plant_master mpm
        ON eoi.MFGFactoryId = mpm.MFG_PLANT_ID
),

-- Step 4: 取得員工名稱
emp_info AS (
    SELECT EmpCode, EmpName
    FROM bronze.common_hr_employee
),

-- Step 5: 組合所有資料
combined AS (
    SELECT 
        eo.EmpCode AS emp_code,
        ei.EmpName AS emp_name,
        eo.Plant AS plant,
        eo.factory AS factory,
        COALESCE(eg.user_group_names, []) AS user_group_names,
        COALESCE(en.node_codes, []) AS node_codes
    FROM emp_org eo
    LEFT JOIN emp_groups eg ON eo.EmpCode = eg.EmpCode
    LEFT JOIN emp_nodes en ON eo.EmpCode = en.EmpCode
    LEFT JOIN emp_info ei ON eo.EmpCode = ei.EmpCode
)

SELECT 
    emp_code,
    -- 根據 NodeCodes 展開 Vx (格式: V1_3, V2_4 等，使用 LIKE 'V1_%')
    arrayJoin(
        arrayFilter(x -> x != '', 
            arrayDistinct(
                arrayFlatten([
                    -- V1 規則
                    if(arrayExists(x -> x LIKE 'V1\\_%', node_codes), ['V1'], []),
                    -- V2 規則
                    if(arrayExists(x -> x LIKE 'V2\\_%', node_codes), ['V2'], []),
                    -- V3 規則（NPE 歸 V1，非 NPE 歸 V3）
                    if(arrayExists(x -> x LIKE 'V3\\_%', node_codes) AND factory LIKE '%NPE%', ['V1'], []),
                    if(arrayExists(x -> x LIKE 'V3\\_%', node_codes) AND factory NOT LIKE '%NPE%', ['V3'], [])
                ])
            )
        )
    ) AS vx_type,
    COALESCE(plant, '') AS plant,
    COALESCE(factory, '') AS factory,
    emp_name,
    
    -- 預計算：成員資格
    -- V1 白名單：User, PMUser, PowerUser
    -- V1 排除：ManagerUser, LocalAdmin, GlobalAdmin, SystemAdmin, InternalAudit, SeniorOfficers&DTO
    CASE 
        -- 排除優先
        WHEN hasAny(user_group_names, ['ManagerUser', 'LocalAdmin', 'GlobalAdmin', 'SystemAdmin', 'InternalAudit', 'SeniorOfficers&DTO'])
        THEN 0
        -- V1 白名單 (需重新計算 vx_type)
        WHEN arrayJoin(arrayFilter(x -> x != '', arrayDistinct(arrayFlatten([
            if(arrayExists(x -> x LIKE 'V1\\_%', node_codes), ['V1'], []),
            if(arrayExists(x -> x LIKE 'V2\\_%', node_codes), ['V2'], []),
            if(arrayExists(x -> x LIKE 'V3\\_%', node_codes) AND factory LIKE '%NPE%', ['V1'], []),
            if(arrayExists(x -> x LIKE 'V3\\_%', node_codes) AND factory NOT LIKE '%NPE%', ['V3'], [])
        ])))) = 'V1' AND hasAny(user_group_names, ['User', 'PMUser', 'PowerUser'])
        THEN 1
        -- V2/V3 只允許 User 且無其他身分
        WHEN arrayJoin(arrayFilter(x -> x != '', arrayDistinct(arrayFlatten([
            if(arrayExists(x -> x LIKE 'V1\\_%', node_codes), ['V1'], []),
            if(arrayExists(x -> x LIKE 'V2\\_%', node_codes), ['V2'], []),
            if(arrayExists(x -> x LIKE 'V3\\_%', node_codes) AND factory LIKE '%NPE%', ['V1'], []),
            if(arrayExists(x -> x LIKE 'V3\\_%', node_codes) AND factory NOT LIKE '%NPE%', ['V3'], [])
        ])))) IN ('V2', 'V3') AND length(user_group_names) = 1 AND has(user_group_names, 'User')
        THEN 1
        ELSE 0
    END AS is_config_user,
    
    -- 是否被排除
    CASE 
        WHEN hasAny(user_group_names, ['ManagerUser', 'LocalAdmin', 'GlobalAdmin', 'SystemAdmin', 'InternalAudit', 'SeniorOfficers&DTO'])
        THEN 1
        ELSE 0
    END AS is_excluded,
    
    -- 排除原因
    CASE 
        WHEN has(user_group_names, 'ManagerUser') THEN 'ManagerUser'
        WHEN has(user_group_names, 'LocalAdmin') THEN 'LocalAdmin'
        WHEN has(user_group_names, 'GlobalAdmin') THEN 'GlobalAdmin'
        WHEN has(user_group_names, 'SystemAdmin') THEN 'SystemAdmin'
        WHEN has(user_group_names, 'InternalAudit') THEN 'InternalAudit'
        WHEN has(user_group_names, 'SeniorOfficers&DTO') THEN 'SeniorOfficers&DTO'
        ELSE NULL
    END AS exclude_reason,
    
    user_group_names,
    hasAny(user_group_names, ['User', 'PMUser', 'PowerUser']) AS has_whitelist_group,
    hasAny(user_group_names, ['ManagerUser', 'LocalAdmin', 'GlobalAdmin', 'SystemAdmin', 'InternalAudit', 'SeniorOfficers&DTO']) AS has_exclude_group,
    node_codes,
    
    now64(3) AS _transform_time

FROM combined
WHERE emp_code IS NOT NULL AND emp_code != ''
"""


def transform_fact_task_vx(client):
    """轉換 FACT_TASK_VX_ATTRIBUTION"""
    logger.info("開始轉換 FACT_TASK_VX_ATTRIBUTION...")
    
    # 清空目標表
    client.command("TRUNCATE TABLE silver.FACT_TASK_VX_ATTRIBUTION")
    
    # 執行轉換
    client.command(TRANSFORM_FACT_TASK_VX_SQL)
    
    # 取得筆數
    count = client.command("SELECT count() FROM silver.FACT_TASK_VX_ATTRIBUTION")
    logger.info(f"FACT_TASK_VX_ATTRIBUTION 轉換完成，共 {count:,} 筆")
    
    return count


def transform_dim_config_user(client):
    """轉換 DIM_CONFIG_USER"""
    logger.info("開始轉換 DIM_CONFIG_USER...")
    
    # 清空目標表
    client.command("TRUNCATE TABLE silver.DIM_CONFIG_USER")
    
    # 執行轉換
    client.command(TRANSFORM_DIM_CONFIG_USER_SQL)
    
    # 取得筆數
    count = client.command("SELECT count() FROM silver.DIM_CONFIG_USER")
    logger.info(f"DIM_CONFIG_USER 轉換完成，共 {count:,} 筆")
    
    return count


def main():
    """主程式"""
    parser = argparse.ArgumentParser(description='Silver 層轉換 - 通用指標')
    parser.add_argument('--table', choices=['task', 'user', 'all'], default='all',
                        help='指定轉換的表：task=任務表, user=用戶表, all=全部')
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Silver 層轉換 - 通用指標")
    logger.info("=" * 60)
    
    start_time = datetime.now()
    
    try:
        client = get_client()
        
        task_count = 0
        user_count = 0
        
        if args.table in ('task', 'all'):
            task_count = transform_fact_task_vx(client)
        
        if args.table in ('user', 'all'):
            user_count = transform_dim_config_user(client)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info(f"轉換完成！")
        if args.table in ('task', 'all'):
            logger.info(f"  FACT_TASK_VX_ATTRIBUTION: {task_count:,} 筆")
        if args.table in ('user', 'all'):
            logger.info(f"  DIM_CONFIG_USER: {user_count:,} 筆")
        logger.info(f"  總耗時: {elapsed:.2f} 秒")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"轉換失敗: {e}")
        raise


if __name__ == "__main__":
    main()
