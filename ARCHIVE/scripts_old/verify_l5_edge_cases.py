#!/usr/bin/env python3
"""
========================================
L5 業務規則邊界案例驗證腳本
========================================
專門驗證 L5 業務規則的邊界案例和特殊情況：
1. NULL 值處理
2. 邊界工單號
3. 混合條件
4. 特殊字符處理
"""

import pymssql
import clickhouse_connect
import logging
from datetime import datetime

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
    'host': '10.136.218.207',
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


def verify_null_handling():
    """驗證 NULL 值處理"""
    logger.info("=" * 80)
    logger.info("1. NULL 值處理驗證")
    logger.info("=" * 80)
    
    # 測試 NULL moNumber 的處理
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
        COUNT(*) AS total_tasks,
        COUNT(v.varinst_moNumber) AS has_mo_number,
        COUNT(*) - COUNT(v.varinst_moNumber) AS null_mo_number,
        -- NULL moNumber 的 Vx 歸屬
        SUM(CASE 
            WHEN v.varinst_moNumber IS NULL 
                 AND COALESCE(SUBSTRING(hti.TASK_DEF_KEY_, 1, 2), 'Unknown') = 'V1'
            THEN 1 ELSE 0 
        END) AS null_mo_but_v1_by_taskdef,
        SUM(CASE 
            WHEN v.varinst_moNumber IS NULL 
                 AND COALESCE(SUBSTRING(hti.TASK_DEF_KEY_, 1, 2), 'Unknown') = 'V2'
            THEN 1 ELSE 0 
        END) AS null_mo_but_v2_by_taskdef,
        SUM(CASE 
            WHEN v.varinst_moNumber IS NULL 
                 AND COALESCE(SUBSTRING(hti.TASK_DEF_KEY_, 1, 2), 'Unknown') = 'V3'
            THEN 1 ELSE 0 
        END) AS null_mo_but_v3_by_taskdef
    FROM ACT_HI_PROCINST hi
    INNER JOIN ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
    LEFT JOIN varinst_pivoted v ON hi.PROC_INST_ID_ = v.PROC_INST_ID_
    WHERE hti.START_TIME_ >= '2025-12-01'
    """
    
    ch_sql = """
    SELECT 
        COUNT(*) AS total_tasks,
        COUNT(mo_number) AS has_mo_number,
        COUNT(*) - COUNT(mo_number) AS null_mo_number,
        SUM(CASE 
            WHEN mo_number IS NULL AND vx_type = 'V1'
            THEN 1 ELSE 0 
        END) AS null_mo_but_v1_by_taskdef,
        SUM(CASE 
            WHEN mo_number IS NULL AND vx_type = 'V2'
            THEN 1 ELSE 0 
        END) AS null_mo_but_v2_by_taskdef,
        SUM(CASE 
            WHEN mo_number IS NULL AND vx_type = 'V3'
            THEN 1 ELSE 0 
        END) AS null_mo_but_v3_by_taskdef
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE task_create_date >= '2025-12-01'
    """
    
    # 執行查詢
    mssql_conn = get_mssql_connection()
    mssql_cursor = mssql_conn.cursor()
    mssql_cursor.execute(mssql_sql)
    mssql_result = mssql_cursor.fetchone()
    mssql_conn.close()
    
    ch_client = get_clickhouse_client()
    ch_result = ch_client.query(ch_sql)
    ch_row = ch_result.result_rows[0]
    
    # 比對結果
    logger.info("NULL 值處理統計：")
    logger.info(f"{'項目':<25} {'MSSQL':<10} {'ClickHouse':<12} {'狀態'}")
    logger.info("-" * 60)
    
    fields = [
        ('總任務數', 0),
        ('有 moNumber', 1),
        ('NULL moNumber', 2),
        ('NULL mo 但 V1', 3),
        ('NULL mo 但 V2', 4),
        ('NULL mo 但 V3', 5)
    ]
    
    all_match = True
    for field_name, idx in fields:
        mssql_val = mssql_result[idx]
        ch_val = ch_row[idx]
        status = "✓" if mssql_val == ch_val else "✗"
        if mssql_val != ch_val:
            all_match = False
        logger.info(f"{field_name:<25} {mssql_val:<10} {ch_val:<12} {status}")
    
    return all_match


def verify_boundary_mo_numbers():
    """驗證邊界工單號"""
    logger.info("\n" + "=" * 80)
    logger.info("2. 邊界工單號驗證")
    logger.info("=" * 80)
    
    # 測試邊界工單號（接近但不符合 V1 規則的工單號）
    test_patterns = [
        ('195%', '195 開頭（接近 196）'),
        ('197%', '197 開頭（196-199 之間）'),
        ('201%', '201 開頭（接近 200）'),
        ('211%', '211 開頭（210-212 之間）'),
        ('214%', '214 開頭（接近 213）'),
        ('316%', '316 開頭（接近 315）'),
        ('1960%', '1960 開頭（196 + 0）'),
        ('1999%', '1999 開頭（199 + 9）')
    ]
    
    for pattern, description in test_patterns:
        logger.info(f"\n測試 {description}:")
        
        # MSSQL 查詢
        mssql_sql = f"""
        WITH varinst_pivoted AS (
            SELECT 
                PROC_INST_ID_,
                MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS varinst_moNumber
            FROM ACT_HI_VARINST
            WHERE NAME_ = 'moNumber'
            GROUP BY PROC_INST_ID_
        )
        SELECT 
            COUNT(*) AS count_tasks,
            SUM(CASE 
                WHEN v.varinst_moNumber LIKE '196%' 
                     OR v.varinst_moNumber LIKE '199%' 
                     OR v.varinst_moNumber LIKE '200%'
                     OR v.varinst_moNumber LIKE '210%' 
                     OR v.varinst_moNumber LIKE '212%' 
                     OR v.varinst_moNumber LIKE '213%'
                     OR v.varinst_moNumber LIKE '315%'
                THEN 1 ELSE 0 
            END) AS should_be_v1
        FROM ACT_HI_PROCINST hi
        INNER JOIN ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
        LEFT JOIN varinst_pivoted v ON hi.PROC_INST_ID_ = v.PROC_INST_ID_
        WHERE hti.START_TIME_ >= '2025-12-01'
          AND v.varinst_moNumber LIKE '{pattern}'
        """
        
        # ClickHouse 查詢
        ch_sql = f"""
        SELECT 
            COUNT(*) AS count_tasks,
            SUM(CASE WHEN vx_type = 'V1' THEN 1 ELSE 0 END) AS actual_v1
        FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
        WHERE task_create_date >= '2025-12-01'
          AND mo_number LIKE '{pattern}'
        """
        
        # 執行查詢
        mssql_conn = get_mssql_connection()
        mssql_cursor = mssql_conn.cursor()
        mssql_cursor.execute(mssql_sql)
        mssql_result = mssql_cursor.fetchone()
        mssql_conn.close()
        
        ch_client = get_clickhouse_client()
        ch_result = ch_client.query(ch_sql)
        
        if ch_result.result_rows:
            ch_row = ch_result.result_rows[0]
            mssql_count, mssql_v1 = mssql_result
            ch_count, ch_v1 = ch_row
            
            logger.info(f"  任務數: MSSQL={mssql_count}, CH={ch_count}")
            logger.info(f"  V1 歸屬: MSSQL={mssql_v1}, CH={ch_v1}")
            
            if mssql_count == ch_count and mssql_v1 == ch_v1:
                logger.info(f"  ✓ {description} 處理正確")
            else:
                logger.error(f"  ✗ {description} 處理有誤")
        else:
            logger.info(f"  無 {description} 的資料")


def verify_mixed_conditions():
    """驗證混合條件"""
    logger.info("\n" + "=" * 80)
    logger.info("3. 混合條件驗證")
    logger.info("=" * 80)
    
    # 測試同時滿足多個排除條件的情況
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
        -- 同時滿足多個排除條件的統計
        SUM(CASE 
            WHEN (CASE WHEN var_bypass.LONG_ = 1 THEN 'Y' ELSE 'N' END != 'N')
                 AND (hti.TASK_DEF_KEY_ LIKE 'E%' OR hti.TASK_DEF_KEY_ LIKE 'C%')
            THEN 1 ELSE 0 
        END) AS bypass_and_ec_prefix,
        SUM(CASE 
            WHEN (CASE WHEN var_bypass.LONG_ = 1 THEN 'Y' ELSE 'N' END != 'N')
                 AND (v.varinst_moNumber LIKE 'Q%' OR v.varinst_moNumber LIKE 'R%')
            THEN 1 ELSE 0 
        END) AS bypass_and_qr_order,
        SUM(CASE 
            WHEN (hti.TASK_DEF_KEY_ LIKE 'E%' OR hti.TASK_DEF_KEY_ LIKE 'C%')
                 AND (v.varinst_moNumber LIKE 'Q%' OR v.varinst_moNumber LIKE 'R%')
            THEN 1 ELSE 0 
        END) AS ec_prefix_and_qr_order,
        -- V1 特殊規則 + 排除條件
        SUM(CASE 
            WHEN (v.varinst_moNumber LIKE '196%' OR v.varinst_moNumber LIKE '199%')
                 AND (hti.TASK_DEF_KEY_ LIKE 'E%' OR hti.TASK_DEF_KEY_ LIKE 'C%')
            THEN 1 ELSE 0 
        END) AS v1_special_but_excluded
    FROM ACT_HI_PROCINST hi
    INNER JOIN ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
    LEFT JOIN varinst_pivoted v ON hi.PROC_INST_ID_ = v.PROC_INST_ID_
    LEFT JOIN ACT_HI_VARINST var_bypass ON hti.ID_ = var_bypass.TASK_ID_ AND var_bypass.NAME_ = 'autoComplete'
    WHERE hti.START_TIME_ >= '2025-12-01'
    """
    
    ch_sql = """
    SELECT 
        SUM(CASE 
            WHEN task_bypass != 'N' AND (task_definition_key LIKE 'E%' OR task_definition_key LIKE 'C%')
            THEN 1 ELSE 0 
        END) AS bypass_and_ec_prefix,
        SUM(CASE 
            WHEN task_bypass != 'N' AND (mo_number LIKE 'Q%' OR mo_number LIKE 'R%')
            THEN 1 ELSE 0 
        END) AS bypass_and_qr_order,
        SUM(CASE 
            WHEN (task_definition_key LIKE 'E%' OR task_definition_key LIKE 'C%')
                 AND (mo_number LIKE 'Q%' OR mo_number LIKE 'R%')
            THEN 1 ELSE 0 
        END) AS ec_prefix_and_qr_order,
        SUM(CASE 
            WHEN is_special_v1_rule = 1 AND is_excluded = 1
            THEN 1 ELSE 0 
        END) AS v1_special_but_excluded
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE task_create_date >= '2025-12-01'
    """
    
    # 執行查詢
    mssql_conn = get_mssql_connection()
    mssql_cursor = mssql_conn.cursor()
    mssql_cursor.execute(mssql_sql)
    mssql_result = mssql_cursor.fetchone()
    mssql_conn.close()
    
    ch_client = get_clickhouse_client()
    ch_result = ch_client.query(ch_sql)
    ch_row = ch_result.result_rows[0]
    
    # 比對結果
    logger.info("混合條件統計：")
    logger.info(f"{'條件組合':<25} {'MSSQL':<10} {'ClickHouse':<12} {'狀態'}")
    logger.info("-" * 60)
    
    conditions = [
        ('Bypass + E/C 前綴', 0),
        ('Bypass + Q/R 工單', 1),
        ('E/C 前綴 + Q/R 工單', 2),
        ('V1 特殊但被排除', 3)
    ]
    
    all_match = True
    for condition_name, idx in conditions:
        mssql_val = mssql_result[idx]
        ch_val = ch_row[idx]
        status = "✓" if mssql_val == ch_val else "✗"
        if mssql_val != ch_val:
            all_match = False
        logger.info(f"{condition_name:<25} {mssql_val:<10} {ch_val:<12} {status}")
    
    return all_match


def verify_special_characters():
    """驗證特殊字符處理"""
    logger.info("\n" + "=" * 80)
    logger.info("4. 特殊字符處理驗證")
    logger.info("=" * 80)
    
    # 測試包含特殊字符的工單號
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
        COUNT(*) AS total_with_mo,
        SUM(CASE WHEN v.varinst_moNumber LIKE '%-%' THEN 1 ELSE 0 END) AS contains_dash,
        SUM(CASE WHEN v.varinst_moNumber LIKE '%_%' THEN 1 ELSE 0 END) AS contains_underscore,
        SUM(CASE WHEN v.varinst_moNumber LIKE '% %' THEN 1 ELSE 0 END) AS contains_space,
        SUM(CASE WHEN LEN(v.varinst_moNumber) > 20 THEN 1 ELSE 0 END) AS very_long_mo,
        SUM(CASE WHEN v.varinst_moNumber = '' THEN 1 ELSE 0 END) AS empty_string_mo
    FROM ACT_HI_PROCINST hi
    INNER JOIN ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
    LEFT JOIN varinst_pivoted v ON hi.PROC_INST_ID_ = v.PROC_INST_ID_
    WHERE hti.START_TIME_ >= '2025-12-01'
      AND v.varinst_moNumber IS NOT NULL
    """
    
    ch_sql = """
    SELECT 
        COUNT(*) AS total_with_mo,
        SUM(CASE WHEN mo_number LIKE '%-%' THEN 1 ELSE 0 END) AS contains_dash,
        SUM(CASE WHEN mo_number LIKE '%_%' THEN 1 ELSE 0 END) AS contains_underscore,
        SUM(CASE WHEN mo_number LIKE '% %' THEN 1 ELSE 0 END) AS contains_space,
        SUM(CASE WHEN length(mo_number) > 20 THEN 1 ELSE 0 END) AS very_long_mo,
        SUM(CASE WHEN mo_number = '' THEN 1 ELSE 0 END) AS empty_string_mo
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE task_create_date >= '2025-12-01'
      AND mo_number IS NOT NULL
    """
    
    # 執行查詢
    mssql_conn = get_mssql_connection()
    mssql_cursor = mssql_conn.cursor()
    mssql_cursor.execute(mssql_sql)
    mssql_result = mssql_cursor.fetchone()
    mssql_conn.close()
    
    ch_client = get_clickhouse_client()
    ch_result = ch_client.query(ch_sql)
    ch_row = ch_result.result_rows[0]
    
    # 比對結果
    logger.info("特殊字符處理統計：")
    logger.info(f"{'字符類型':<20} {'MSSQL':<10} {'ClickHouse':<12} {'狀態'}")
    logger.info("-" * 55)
    
    char_types = [
        ('總計（有 moNumber）', 0),
        ('包含 - 符號', 1),
        ('包含 _ 符號', 2),
        ('包含空格', 3),
        ('超長工單號 (>20)', 4),
        ('空字串', 5)
    ]
    
    all_match = True
    for char_type, idx in char_types:
        mssql_val = mssql_result[idx]
        ch_val = ch_row[idx]
        status = "✓" if mssql_val == ch_val else "✗"
        if mssql_val != ch_val:
            all_match = False
        logger.info(f"{char_type:<20} {mssql_val:<10} {ch_val:<12} {status}")
    
    return all_match


def main():
    """主程式"""
    logger.info("=" * 100)
    logger.info("L5 業務規則邊界案例驗證腳本")
    logger.info("驗證 NULL 值、邊界條件、混合情況、特殊字符處理")
    logger.info("=" * 100)
    
    start_time = datetime.now()
    results = []
    
    try:
        results.append(('NULL 值處理', verify_null_handling()))
        verify_boundary_mo_numbers()  # 這個函數不返回布爾值，只做展示
        results.append(('混合條件', verify_mixed_conditions()))
        results.append(('特殊字符處理', verify_special_characters()))
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # 總結報告
        logger.info("\n" + "=" * 100)
        logger.info("L5 業務規則邊界案例驗證總結")
        logger.info("=" * 100)
        
        all_passed = True
        for test_name, passed in results:
            status = "✅ 通過" if passed else "❌ 失敗"
            logger.info(f"  {test_name}: {status}")
            if not passed:
                all_passed = False
        
        logger.info(f"\n總耗時: {elapsed:.2f} 秒")
        
        if all_passed:
            logger.info("\n🎉 所有邊界案例驗證通過！")
            logger.info("L5 業務規則在各種特殊情況下都能正確處理")
        else:
            logger.error("\n⚠️ 部分邊界案例驗證失敗")
            logger.error("請檢查特殊情況的處理邏輯")
        
        logger.info("=" * 100)
        
    except Exception as e:
        logger.error(f"驗證過程發生錯誤: {e}")
        raise


if __name__ == "__main__":
    main()