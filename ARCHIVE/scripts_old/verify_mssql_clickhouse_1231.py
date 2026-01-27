#!/usr/bin/env python3
"""
========================================
MSSQL vs ClickHouse 12/31 資料驗證
========================================
用途：驗證 2025-12-31 的資料在 MSSQL 和 ClickHouse 中是否一致
檢查項目：
1. 總筆數比較
2. TaskId 比較
3. 狀態分布比較
4. V1 子類型分類比較

使用方式：
- python scripts/verify_mssql_clickhouse_1231.py
"""

import pymssql
import clickhouse_connect
from datetime import datetime
import logging

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 連線設定
MSSQL_CONFIG = {
    'server': 'twtpesqldv2.delta.corp',
    'port': '1433',
    'user': 'DMP_APP_SRV',
    'password': 'APP@DB#01',
    'database': 'APP_SRV_BPM'
}

CH_CONFIG = {
    'host': 'REDACTED_IP',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}


def get_mssql_data():
    """取得 MSSQL 12/31 資料"""
    logger.info("連接 MSSQL 並取得 12/31 資料...")
    
    conn = pymssql.connect(**MSSQL_CONFIG)
    cursor = conn.cursor()
    
    # MSSQL 查詢 - 12/31 的任務資料
    cursor.execute("""
        SELECT 
            hti.ID_ AS taskId,
            CASE
                WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
                WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
                ELSE 'TODO'
            END AS taskStatus,
            CASE WHEN var_bypass.LONG_ = 1 THEN 'Y' ELSE 'N' END AS taskBypass,
            ISNULL(var_plant.TEXT_, '') AS plant,
            ISNULL(var_lineName.TEXT_, '') AS line,
            ISNULL(var_factory.TEXT_, '') AS factory,
            ISNULL(var_moNumber.TEXT_, '') AS moNumber,
            hti.TASK_DEF_KEY_ AS taskDefinitionKey,
            CONVERT(DATE, hti.START_TIME_) AS taskCreateDate
        FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
        INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant' AND var_plant.TASK_ID_ IS NULL
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName' AND var_lineName.TASK_ID_ IS NULL
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory' AND var_factory.TASK_ID_ IS NULL
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_moNumber ON hi.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ AND var_moNumber.NAME_ = 'moNumber' AND var_moNumber.TASK_ID_ IS NULL
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_bypass ON hti.ID_ = var_bypass.TASK_ID_ AND var_bypass.NAME_ = 'autoComplete'
        WHERE CONVERT(DATE, hti.START_TIME_) = '2025-12-31'
        ORDER BY hti.ID_
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    logger.info(f"MSSQL 取得 {len(rows)} 筆 12/31 資料")
    return rows


def get_clickhouse_data():
    """取得 ClickHouse 12/31 資料"""
    logger.info("連接 ClickHouse 並取得 12/31 資料...")
    
    client = clickhouse_connect.get_client(**CH_CONFIG)
    
    # ClickHouse 查詢 - 使用 FACT_TASK_VX_ATTRIBUTION 表
    result = client.query("""
        SELECT 
            task_id,
            task_status,
            task_bypass,
            plant,
            line,
            factory,
            mo_number,
            task_definition_key,
            task_create_date
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE task_create_date = '2025-12-31'
        ORDER BY task_id
    """)
    
    logger.info(f"ClickHouse 取得 {len(result.result_rows)} 筆 12/31 資料")
    return result.result_rows


def analyze_vx_classification(mssql_data, ch_data):
    """分析 Vx 分類邏輯"""
    logger.info("分析 Vx 分類邏輯...")
    
    # 建立 MSSQL 資料字典
    mssql_dict = {}
    for row in mssql_data:
        task_id = row[0]
        mo_number = row[6]
        task_def_key = row[7]
        
        # 計算 Vx 類型（模擬 ClickHouse 邏輯）
        if (mo_number and (mo_number.startswith('196') or mo_number.startswith('199') or 
                          mo_number.startswith('200') or mo_number.startswith('210') or 
                          mo_number.startswith('212') or mo_number.startswith('213') or 
                          mo_number.startswith('315'))):
            vx_type = 'V1'
        else:
            vx_type = task_def_key[:2] if task_def_key else 'Unknown'
        
        mssql_dict[task_id] = {
            'vx_type': vx_type,
            'mo_number': mo_number,
            'factory': row[5]
        }
    
    # 建立 ClickHouse 資料字典
    ch_dict = {}
    for row in ch_data:
        task_id = row[0]
        ch_dict[task_id] = {
            'mo_number': row[6],
            'factory': row[5]
        }
    
    # 比較共同的 task_id
    common_tasks = set(mssql_dict.keys()) & set(ch_dict.keys())
    logger.info(f"共同任務數: {len(common_tasks)}")
    
    # 分析 V1 子類型
    v1_tasks = [tid for tid in common_tasks if mssql_dict[tid]['vx_type'] == 'V1']
    logger.info(f"V1 任務數: {len(v1_tasks)}")
    
    v1_npe_count = 0
    v1_mfg_count = 0
    
    for task_id in v1_tasks:
        factory = mssql_dict[task_id]['factory']
        if factory and 'NPE' in factory:
            v1_npe_count += 1
        else:
            v1_mfg_count += 1
    
    logger.info(f"V1_NPE: {v1_npe_count} 筆")
    logger.info(f"V1_MFG: {v1_mfg_count} 筆")
    
    return {
        'total_v1': len(v1_tasks),
        'v1_npe': v1_npe_count,
        'v1_mfg': v1_mfg_count
    }


def compare_data(mssql_data, ch_data):
    """比較 MSSQL 和 ClickHouse 資料"""
    logger.info("=" * 60)
    logger.info("比較 MSSQL vs ClickHouse 資料")
    logger.info("=" * 60)
    
    # 1. 總筆數比較
    logger.info(f"總筆數比較:")
    logger.info(f"  MSSQL: {len(mssql_data):,} 筆")
    logger.info(f"  ClickHouse: {len(ch_data):,} 筆")
    logger.info(f"  差異: {abs(len(mssql_data) - len(ch_data)):,} 筆")
    
    # 2. TaskId 比較
    mssql_task_ids = {row[0] for row in mssql_data}
    ch_task_ids = {row[0] for row in ch_data}
    
    only_in_mssql = mssql_task_ids - ch_task_ids
    only_in_ch = ch_task_ids - mssql_task_ids
    common_tasks = mssql_task_ids & ch_task_ids
    
    logger.info(f"\nTaskId 比較:")
    logger.info(f"  共同任務: {len(common_tasks):,} 筆")
    logger.info(f"  只在 MSSQL: {len(only_in_mssql):,} 筆")
    logger.info(f"  只在 ClickHouse: {len(only_in_ch):,} 筆")
    
    if only_in_mssql:
        logger.info(f"  MSSQL 獨有範例: {list(only_in_mssql)[:5]}")
    if only_in_ch:
        logger.info(f"  ClickHouse 獨有範例: {list(only_in_ch)[:5]}")
    
    # 3. 狀態分布比較
    mssql_status_counts = {}
    for row in mssql_data:
        status = row[1]
        mssql_status_counts[status] = mssql_status_counts.get(status, 0) + 1
    
    ch_status_counts = {}
    for row in ch_data:
        status = row[1]
        ch_status_counts[status] = ch_status_counts.get(status, 0) + 1
    
    logger.info(f"\n狀態分布比較:")
    all_statuses = set(mssql_status_counts.keys()) | set(ch_status_counts.keys())
    for status in sorted(all_statuses):
        mssql_cnt = mssql_status_counts.get(status, 0)
        ch_cnt = ch_status_counts.get(status, 0)
        match = "✅" if mssql_cnt == ch_cnt else "❌"
        logger.info(f"  {status}: MSSQL={mssql_cnt:,}, ClickHouse={ch_cnt:,} {match}")
    
    # 4. Bypass 分布比較
    mssql_bypass_counts = {}
    for row in mssql_data:
        bypass = row[2]
        mssql_bypass_counts[bypass] = mssql_bypass_counts.get(bypass, 0) + 1
    
    ch_bypass_counts = {}
    for row in ch_data:
        bypass = row[2]
        ch_bypass_counts[bypass] = ch_bypass_counts.get(bypass, 0) + 1
    
    logger.info(f"\nBypass 分布比較:")
    all_bypass = set(mssql_bypass_counts.keys()) | set(ch_bypass_counts.keys())
    for bypass in sorted(all_bypass):
        mssql_cnt = mssql_bypass_counts.get(bypass, 0)
        ch_cnt = ch_bypass_counts.get(bypass, 0)
        match = "✅" if mssql_cnt == ch_cnt else "❌"
        logger.info(f"  {bypass}: MSSQL={mssql_cnt:,}, ClickHouse={ch_cnt:,} {match}")
    
    # 5. V1 子類型分析
    v1_analysis = analyze_vx_classification(mssql_data, ch_data)
    logger.info(f"\nV1 子類型分析:")
    logger.info(f"  總 V1 任務: {v1_analysis['total_v1']:,} 筆")
    logger.info(f"  V1_NPE: {v1_analysis['v1_npe']:,} 筆")
    logger.info(f"  V1_MFG: {v1_analysis['v1_mfg']:,} 筆")
    
    # 總結
    is_consistent = (
        len(mssql_data) == len(ch_data) and
        len(only_in_mssql) == 0 and
        len(only_in_ch) == 0 and
        all(mssql_status_counts.get(s, 0) == ch_status_counts.get(s, 0) for s in all_statuses)
    )
    
    return is_consistent


def main():
    """主程式"""
    logger.info("=" * 80)
    logger.info("MSSQL vs ClickHouse 12/31 資料驗證")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    try:
        # 取得資料
        mssql_data = get_mssql_data()
        ch_data = get_clickhouse_data()
        
        # 比較資料
        is_consistent = compare_data(mssql_data, ch_data)
        
        # 總結
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info("=" * 80)
        logger.info("驗證結果總結")
        logger.info("=" * 80)
        
        if is_consistent:
            logger.info("🎉 驗證通過！MSSQL 與 ClickHouse 12/31 資料完全一致")
        else:
            logger.warning("⚠️ 驗證失敗！MSSQL 與 ClickHouse 資料存在差異")
        
        logger.info(f"總耗時: {elapsed:.2f} 秒")
        
        return is_consistent
        
    except Exception as e:
        logger.error(f"驗證過程發生錯誤: {e}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)