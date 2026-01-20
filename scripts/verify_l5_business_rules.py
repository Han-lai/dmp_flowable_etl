#!/usr/bin/env python3
"""
========================================
L5 業務規則驗證腳本
========================================
驗證 L5 任務執行完成率指標的核心業務規則：
1. Vx 歸屬規則驗證
2. 工單號判斷邏輯驗證
3. 排除邏輯驗證

對比 MSSQL 原始邏輯與 ClickHouse Silver 層實作
"""

import pymssql
import clickhouse_connect
import logging
from datetime import datetime
import argparse

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


def get_mssql_connection():
    """建立 MSSQL 連線"""
    return pymssql.connect(**MSSQL_CONFIG)


def get_clickhouse_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(**CH_CONFIG)


# ============================================
# 1. Vx 歸屬規則驗證
# ============================================

def verify_vx_attribution_rules():
    """驗證 Vx 歸屬規則"""
    logger.info("=" * 80)
    logger.info("1. Vx 歸屬規則驗證")
    logger.info("=" * 80)
    
    # MSSQL 查詢：實作 Vx 歸屬邏輯
    mssql_sql = """
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS varinst_moNumber
        FROM ACT_HI_VARINST
        WHERE NAME_ = 'moNumber'
        GROUP BY PROC_INST_ID_
    )
    SELECT 
        hti.ID_ AS task_id,
        hti.TASK_DEF_KEY_ AS task_definition_key,
        v.varinst_moNumber,
        hi.BUSINESS_KEY_,
        -- Vx 歸屬邏輯
        CASE 
            WHEN v.varinst_moNumber LIKE '196%' 
                 OR v.varinst_moNumber LIKE '199%' 
                 OR v.varinst_moNumber LIKE '200%'
                 OR v.varinst_moNumber LIKE '210%' 
                 OR v.varinst_moNumber LIKE '212%' 
                 OR v.varinst_moNumber LIKE '213%'
                 OR v.varinst_moNumber LIKE '315%'
            THEN 'V1'
            ELSE COALESCE(SUBSTRING(hti.TASK_DEF_KEY_, 1, 2), 'Unknown')
        END AS vx_type_calculated,
        -- V1 子類型
        CASE 
            WHEN (v.varinst_moNumber LIKE '196%' 
                  OR v.varinst_moNumber LIKE '199%' 
                  OR v.varinst_moNumber LIKE '200%'
                  OR v.varinst_moNumber LIKE '210%' 
                  OR v.varinst_moNumber LIKE '212%' 
                  OR v.varinst_moNumber LIKE '213%'
                  OR v.varinst_moNumber LIKE '315%')
                 AND hi.BUSINESS_KEY_ LIKE '%NPE%'
            THEN 'V1_NPE'
            WHEN (v.varinst_moNumber LIKE '196%' 
                  OR v.varinst_moNumber LIKE '199%' 
                  OR v.varinst_moNumber LIKE '200%'
                  OR v.varinst_moNumber LIKE '210%' 
                  OR v.varinst_moNumber LIKE '212%' 
                  OR v.varinst_moNumber LIKE '213%'
                  OR v.varinst_moNumber LIKE '315%')
            THEN 'V1_MFG'
            ELSE NULL
        END AS vx_subtype_calculated,
        -- 是否套用特殊 V1 規則
        CASE 
            WHEN v.varinst_moNumber LIKE '196%' 
                 OR v.varinst_moNumber LIKE '199%' 
                 OR v.varinst_moNumber LIKE '200%'
                 OR v.varinst_moNumber LIKE '210%' 
                 OR v.varinst_moNumber LIKE '212%' 
                 OR v.varinst_moNumber LIKE '213%'
                 OR v.varinst_moNumber LIKE '315%'
            THEN 1
            ELSE 0
        END AS is_special_v1_rule_calculated
    FROM ACT_HI_PROCINST hi
    INNER JOIN ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
    LEFT JOIN varinst_pivoted v ON hi.PROC_INST_ID_ = v.PROC_INST_ID_
    WHERE hti.START_TIME_ >= '2025-12-01'
      AND hti.ID_ IS NOT NULL
    """
    
    # ClickHouse 查詢：Silver 層結果
    ch_sql = """
    SELECT 
        task_id,
        task_definition_key,
        mo_number AS varinst_moNumber,
        business_key,
        vx_type,
        vx_subtype,
        is_special_v1_rule
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE task_create_date >= '2025-12-01'
      AND task_id IS NOT NULL
    """
    
    # 執行查詢
    logger.info("執行 MSSQL 查詢...")
    mssql_conn = get_mssql_connection()
    mssql_cursor = mssql_conn.cursor()
    mssql_cursor.execute(mssql_sql)
    mssql_rows = mssql_cursor.fetchall()
    mssql_conn.close()
    
    logger.info("執行 ClickHouse 查詢...")
    ch_client = get_clickhouse_client()
    ch_result = ch_client.query(ch_sql)
    
    # 建立對照字典
    mssql_dict = {}
    for row in mssql_rows:
        task_id = row[0]
        mssql_dict[task_id] = {
            'task_definition_key': row[1],
            'varinst_moNumber': row[2],
            'business_key': row[3],
            'vx_type': row[4],
            'vx_subtype': row[5],
            'is_special_v1_rule': row[6]
        }
    
    ch_dict = {}
    for row in ch_result.result_rows:
        task_id = row[0]
        ch_dict[task_id] = {
            'task_definition_key': row[1],
            'varinst_moNumber': row[2],
            'business_key': row[3],
            'vx_type': row[4],
            'vx_subtype': row[5],
            'is_special_v1_rule': row[6]
        }
    
    # 比對結果
    logger.info(f"MSSQL 筆數: {len(mssql_rows):,}")
    logger.info(f"ClickHouse 筆數: {len(ch_result.result_rows):,}")
    
    # 找出共同的 task_id
    mssql_ids = set(mssql_dict.keys())
    ch_ids = set(ch_dict.keys())
    common_ids = mssql_ids & ch_ids
    
    logger.info(f"共同 task_id: {len(common_ids):,}")
    
    # 驗證 Vx 歸屬規則
    vx_type_mismatch = []
    vx_subtype_mismatch = []
    special_v1_mismatch = []
    
    for task_id in common_ids:
        mssql_data = mssql_dict[task_id]
        ch_data = ch_dict[task_id]
        
        # 比對 vx_type
        if mssql_data['vx_type'] != ch_data['vx_type']:
            vx_type_mismatch.append({
                'task_id': task_id,
                'mssql': mssql_data['vx_type'],
                'ch': ch_data['vx_type'],
                'mo_number': mssql_data['varinst_moNumber'],
                'task_def_key': mssql_data['task_definition_key']
            })
        
        # 比對 vx_subtype
        if mssql_data['vx_subtype'] != ch_data['vx_subtype']:
            vx_subtype_mismatch.append({
                'task_id': task_id,
                'mssql': mssql_data['vx_subtype'],
                'ch': ch_data['vx_subtype'],
                'business_key': mssql_data['business_key']
            })
        
        # 比對 is_special_v1_rule
        if mssql_data['is_special_v1_rule'] != ch_data['is_special_v1_rule']:
            special_v1_mismatch.append({
                'task_id': task_id,
                'mssql': mssql_data['is_special_v1_rule'],
                'ch': ch_data['is_special_v1_rule'],
                'mo_number': mssql_data['varinst_moNumber']
            })
    
    # 輸出結果
    logger.info("\n" + "=" * 60)
    logger.info("Vx 歸屬規則驗證結果")
    logger.info("=" * 60)
    
    if not vx_type_mismatch:
        logger.info("✅ vx_type 歸屬規則：100% 一致")
    else:
        logger.error(f"❌ vx_type 歸屬規則：{len(vx_type_mismatch)} 筆不一致")
        for i, item in enumerate(vx_type_mismatch[:5]):
            logger.error(f"  {i+1}. {item['task_id']}: MSSQL={item['mssql']}, CH={item['ch']}, mo={item['mo_number']}")
    
    if not vx_subtype_mismatch:
        logger.info("✅ vx_subtype 子類型規則：100% 一致")
    else:
        logger.error(f"❌ vx_subtype 子類型規則：{len(vx_subtype_mismatch)} 筆不一致")
        for i, item in enumerate(vx_subtype_mismatch[:5]):
            logger.error(f"  {i+1}. {item['task_id']}: MSSQL={item['mssql']}, CH={item['ch']}, biz_key={item['business_key']}")
    
    if not special_v1_mismatch:
        logger.info("✅ 特殊 V1 規則標記：100% 一致")
    else:
        logger.error(f"❌ 特殊 V1 規則標記：{len(special_v1_mismatch)} 筆不一致")
        for i, item in enumerate(special_v1_mismatch[:5]):
            logger.error(f"  {i+1}. {item['task_id']}: MSSQL={item['mssql']}, CH={item['ch']}, mo={item['mo_number']}")
    
    return len(vx_type_mismatch) == 0 and len(vx_subtype_mismatch) == 0 and len(special_v1_mismatch) == 0


# ============================================
# 2. 工單號判斷邏輯驗證
# ============================================

def verify_mo_number_logic():
    """驗證工單號判斷邏輯"""
    logger.info("\n" + "=" * 80)
    logger.info("2. 工單號判斷邏輯驗證")
    logger.info("=" * 80)
    
    # 驗證 varinst.moNumber 的使用
    mssql_sql = """
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS varinst_moNumber
        FROM ACT_HI_VARINST
        WHERE NAME_ = 'moNumber'
        GROUP BY PROC_INST_ID_
    )
    SELECT 
        hti.ID_ AS task_id,
        v.varinst_moNumber,
        -- 特殊工單號判斷
        CASE 
            WHEN v.varinst_moNumber LIKE '196%' THEN '196_prefix'
            WHEN v.varinst_moNumber LIKE '199%' THEN '199_prefix'
            WHEN v.varinst_moNumber LIKE '200%' THEN '200_prefix'
            WHEN v.varinst_moNumber LIKE '210%' THEN '210_prefix'
            WHEN v.varinst_moNumber LIKE '212%' THEN '212_prefix'
            WHEN v.varinst_moNumber LIKE '213%' THEN '213_prefix'
            WHEN v.varinst_moNumber LIKE '315%' THEN '315_prefix'
            WHEN v.varinst_moNumber LIKE 'Q%' THEN 'Q_prefix'
            WHEN v.varinst_moNumber LIKE 'R%' THEN 'R_prefix'
            ELSE 'other'
        END AS mo_number_category
    FROM ACT_HI_PROCINST hi
    INNER JOIN ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
    LEFT JOIN varinst_pivoted v ON hi.PROC_INST_ID_ = v.PROC_INST_ID_
    WHERE hti.START_TIME_ >= '2025-12-01'
      AND v.varinst_moNumber IS NOT NULL
    """
    
    ch_sql = """
    SELECT 
        task_id,
        mo_number AS varinst_moNumber,
        CASE 
            WHEN mo_number LIKE '196%' THEN '196_prefix'
            WHEN mo_number LIKE '199%' THEN '199_prefix'
            WHEN mo_number LIKE '200%' THEN '200_prefix'
            WHEN mo_number LIKE '210%' THEN '210_prefix'
            WHEN mo_number LIKE '212%' THEN '212_prefix'
            WHEN mo_number LIKE '213%' THEN '213_prefix'
            WHEN mo_number LIKE '315%' THEN '315_prefix'
            WHEN mo_number LIKE 'Q%' THEN 'Q_prefix'
            WHEN mo_number LIKE 'R%' THEN 'R_prefix'
            ELSE 'other'
        END AS mo_number_category
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE task_create_date >= '2025-12-01'
      AND mo_number IS NOT NULL
    """
    
    # 執行查詢
    logger.info("執行工單號邏輯驗證...")
    mssql_conn = get_mssql_connection()
    mssql_cursor = mssql_conn.cursor()
    mssql_cursor.execute(mssql_sql)
    mssql_rows = mssql_cursor.fetchall()
    mssql_conn.close()
    
    ch_client = get_clickhouse_client()
    ch_result = ch_client.query(ch_sql)
    
    # 統計各類工單號分布
    mssql_stats = {}
    for row in mssql_rows:
        category = row[2]
        mssql_stats[category] = mssql_stats.get(category, 0) + 1
    
    ch_stats = {}
    for row in ch_result.result_rows:
        category = row[2]
        ch_stats[category] = ch_stats.get(category, 0) + 1
    
    # 比對統計結果
    logger.info("\n工單號分布統計：")
    logger.info(f"{'類別':<15} {'MSSQL':<10} {'ClickHouse':<12} {'狀態'}")
    logger.info("-" * 50)
    
    all_categories = set(mssql_stats.keys()) | set(ch_stats.keys())
    all_match = True
    
    for category in sorted(all_categories):
        mssql_count = mssql_stats.get(category, 0)
        ch_count = ch_stats.get(category, 0)
        status = "✓" if mssql_count == ch_count else "✗"
        if mssql_count != ch_count:
            all_match = False
        logger.info(f"{category:<15} {mssql_count:<10} {ch_count:<12} {status}")
    
    # 特別關注 V1 特殊工單號
    v1_categories = ['196_prefix', '199_prefix', '200_prefix', '210_prefix', '212_prefix', '213_prefix', '315_prefix']
    v1_mssql_total = sum(mssql_stats.get(cat, 0) for cat in v1_categories)
    v1_ch_total = sum(ch_stats.get(cat, 0) for cat in v1_categories)
    
    logger.info(f"\nV1 特殊工單號總計：")
    logger.info(f"  MSSQL: {v1_mssql_total:,}")
    logger.info(f"  ClickHouse: {v1_ch_total:,}")
    logger.info(f"  狀態: {'✓' if v1_mssql_total == v1_ch_total else '✗'}")
    
    if all_match:
        logger.info("✅ 工單號判斷邏輯：100% 一致")
    else:
        logger.error("❌ 工單號判斷邏輯：存在差異")
    
    return all_match


# ============================================
# 3. 排除邏輯驗證
# ============================================

def verify_exclusion_logic():
    """驗證排除邏輯"""
    logger.info("\n" + "=" * 80)
    logger.info("3. 排除邏輯驗證")
    logger.info("=" * 80)
    
    # MSSQL 查詢：實作排除邏輯
    mssql_sql = """
    WITH varinst_pivoted AS (
        SELECT 
            PROC_INST_ID_,
            MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS varinst_moNumber
        FROM ACT_HI_VARINST
        WHERE NAME_ = 'moNumber'
        GROUP BY PROC_INST_ID_
    )
    SELECT 
        hti.ID_ AS task_id,
        hti.TASK_DEF_KEY_ AS task_definition_key,
        v.varinst_moNumber,
        CASE WHEN var_bypass.LONG_ = 1 THEN 'Y' ELSE 'N' END AS task_bypass,
        -- 排除邏輯
        CASE 
            WHEN CASE WHEN var_bypass.LONG_ = 1 THEN 'Y' ELSE 'N' END != 'N' THEN 1
            WHEN hti.TASK_DEF_KEY_ LIKE 'E%' OR hti.TASK_DEF_KEY_ LIKE 'C%' THEN 1
            WHEN v.varinst_moNumber LIKE 'Q%' OR v.varinst_moNumber LIKE 'R%' THEN 1
            ELSE 0
        END AS is_excluded_calculated,
        -- 排除原因
        CASE 
            WHEN CASE WHEN var_bypass.LONG_ = 1 THEN 'Y' ELSE 'N' END != 'N' THEN 'bypass'
            WHEN hti.TASK_DEF_KEY_ LIKE 'E%' THEN 'E_prefix'
            WHEN hti.TASK_DEF_KEY_ LIKE 'C%' THEN 'C_prefix'
            WHEN v.varinst_moNumber LIKE 'Q%' THEN 'Q_order'
            WHEN v.varinst_moNumber LIKE 'R%' THEN 'R_order'
            ELSE NULL
        END AS exclude_reason_calculated
    FROM ACT_HI_PROCINST hi
    INNER JOIN ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
    LEFT JOIN varinst_pivoted v ON hi.PROC_INST_ID_ = v.PROC_INST_ID_
    LEFT JOIN ACT_HI_VARINST var_bypass ON hti.ID_ = var_bypass.TASK_ID_ AND var_bypass.NAME_ = 'autoComplete'
    WHERE hti.START_TIME_ >= '2025-12-01'
      AND hti.ID_ IS NOT NULL
    """
    
    ch_sql = """
    SELECT 
        task_id,
        task_definition_key,
        mo_number AS varinst_moNumber,
        task_bypass,
        is_excluded,
        exclude_reason
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE task_create_date >= '2025-12-01'
      AND task_id IS NOT NULL
    """
    
    # 執行查詢
    logger.info("執行排除邏輯驗證...")
    mssql_conn = get_mssql_connection()
    mssql_cursor = mssql_conn.cursor()
    mssql_cursor.execute(mssql_sql)
    mssql_rows = mssql_cursor.fetchall()
    mssql_conn.close()
    
    ch_client = get_clickhouse_client()
    ch_result = ch_client.query(ch_sql)
    
    # 建立對照字典
    mssql_dict = {}
    for row in mssql_rows:
        task_id = row[0]
        mssql_dict[task_id] = {
            'task_definition_key': row[1],
            'varinst_moNumber': row[2],
            'task_bypass': row[3],
            'is_excluded': row[4],
            'exclude_reason': row[5]
        }
    
    ch_dict = {}
    for row in ch_result.result_rows:
        task_id = row[0]
        ch_dict[task_id] = {
            'task_definition_key': row[1],
            'varinst_moNumber': row[2],
            'task_bypass': row[3],
            'is_excluded': row[4],
            'exclude_reason': row[5]
        }
    
    # 找出共同的 task_id
    mssql_ids = set(mssql_dict.keys())
    ch_ids = set(ch_dict.keys())
    common_ids = mssql_ids & ch_ids
    
    logger.info(f"共同 task_id: {len(common_ids):,}")
    
    # 驗證排除邏輯
    bypass_mismatch = []
    excluded_mismatch = []
    reason_mismatch = []
    
    for task_id in common_ids:
        mssql_data = mssql_dict[task_id]
        ch_data = ch_dict[task_id]
        
        # 比對 task_bypass
        if mssql_data['task_bypass'] != ch_data['task_bypass']:
            bypass_mismatch.append({
                'task_id': task_id,
                'mssql': mssql_data['task_bypass'],
                'ch': ch_data['task_bypass']
            })
        
        # 比對 is_excluded
        if mssql_data['is_excluded'] != ch_data['is_excluded']:
            excluded_mismatch.append({
                'task_id': task_id,
                'mssql': mssql_data['is_excluded'],
                'ch': ch_data['is_excluded'],
                'task_def_key': mssql_data['task_definition_key'],
                'mo_number': mssql_data['varinst_moNumber'],
                'bypass': mssql_data['task_bypass']
            })
        
        # 比對 exclude_reason
        if mssql_data['exclude_reason'] != ch_data['exclude_reason']:
            reason_mismatch.append({
                'task_id': task_id,
                'mssql': mssql_data['exclude_reason'],
                'ch': ch_data['exclude_reason']
            })
    
    # 統計排除原因分布
    mssql_exclude_stats = {}
    ch_exclude_stats = {}
    
    for data in mssql_dict.values():
        if data['is_excluded'] == 1:
            reason = data['exclude_reason'] or 'unknown'
            mssql_exclude_stats[reason] = mssql_exclude_stats.get(reason, 0) + 1
    
    for data in ch_dict.values():
        if data['is_excluded'] == 1:
            reason = data['exclude_reason'] or 'unknown'
            ch_exclude_stats[reason] = ch_exclude_stats.get(reason, 0) + 1
    
    # 輸出結果
    logger.info("\n" + "=" * 60)
    logger.info("排除邏輯驗證結果")
    logger.info("=" * 60)
    
    if not bypass_mismatch:
        logger.info("✅ task_bypass 判斷：100% 一致")
    else:
        logger.error(f"❌ task_bypass 判斷：{len(bypass_mismatch)} 筆不一致")
    
    if not excluded_mismatch:
        logger.info("✅ is_excluded 判斷：100% 一致")
    else:
        logger.error(f"❌ is_excluded 判斷：{len(excluded_mismatch)} 筆不一致")
        for i, item in enumerate(excluded_mismatch[:5]):
            logger.error(f"  {i+1}. {item['task_id']}: MSSQL={item['mssql']}, CH={item['ch']}")
            logger.error(f"      task_def_key={item['task_def_key']}, mo={item['mo_number']}, bypass={item['bypass']}")
    
    if not reason_mismatch:
        logger.info("✅ exclude_reason 判斷：100% 一致")
    else:
        logger.error(f"❌ exclude_reason 判斷：{len(reason_mismatch)} 筆不一致")
    
    # 排除原因統計
    logger.info("\n排除原因分布統計：")
    logger.info(f"{'原因':<15} {'MSSQL':<10} {'ClickHouse':<12} {'狀態'}")
    logger.info("-" * 50)
    
    all_reasons = set(mssql_exclude_stats.keys()) | set(ch_exclude_stats.keys())
    exclude_stats_match = True
    
    for reason in sorted(all_reasons):
        mssql_count = mssql_exclude_stats.get(reason, 0)
        ch_count = ch_exclude_stats.get(reason, 0)
        status = "✓" if mssql_count == ch_count else "✗"
        if mssql_count != ch_count:
            exclude_stats_match = False
        logger.info(f"{reason:<15} {mssql_count:<10} {ch_count:<12} {status}")
    
    return (len(bypass_mismatch) == 0 and len(excluded_mismatch) == 0 and 
            len(reason_mismatch) == 0 and exclude_stats_match)


# ============================================
# 主程式
# ============================================

def main():
    """主程式"""
    parser = argparse.ArgumentParser(description='L5 業務規則驗證')
    parser.add_argument('--rule', choices=['vx', 'mo', 'exclude', 'all'], default='all',
                        help='指定驗證規則：vx=Vx歸屬, mo=工單號, exclude=排除邏輯, all=全部')
    args = parser.parse_args()
    
    logger.info("=" * 100)
    logger.info("L5 業務規則驗證腳本")
    logger.info("驗證 MSSQL 原始邏輯與 ClickHouse Silver 層實作一致性")
    logger.info("=" * 100)
    
    start_time = datetime.now()
    results = []
    
    try:
        if args.rule in ('vx', 'all'):
            results.append(('Vx 歸屬規則', verify_vx_attribution_rules()))
        
        if args.rule in ('mo', 'all'):
            results.append(('工單號判斷邏輯', verify_mo_number_logic()))
        
        if args.rule in ('exclude', 'all'):
            results.append(('排除邏輯', verify_exclusion_logic()))
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # 總結報告
        logger.info("\n" + "=" * 100)
        logger.info("L5 業務規則驗證總結")
        logger.info("=" * 100)
        
        all_passed = True
        for rule_name, passed in results:
            status = "✅ 通過" if passed else "❌ 失敗"
            logger.info(f"  {rule_name}: {status}")
            if not passed:
                all_passed = False
        
        logger.info(f"\n總耗時: {elapsed:.2f} 秒")
        
        if all_passed:
            logger.info("\n🎉 所有 L5 業務規則驗證通過！")
            logger.info("MSSQL 原始邏輯與 ClickHouse Silver 層實作完全一致")
        else:
            logger.error("\n⚠️ 部分 L5 業務規則驗證失敗")
            logger.error("請檢查 Silver 層轉換邏輯")
        
        logger.info("=" * 100)
        
    except Exception as e:
        logger.error(f"驗證過程發生錯誤: {e}")
        raise


if __name__ == "__main__":
    main()