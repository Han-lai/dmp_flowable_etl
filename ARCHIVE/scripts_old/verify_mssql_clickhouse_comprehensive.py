#!/usr/bin/env python3
"""
========================================
MSSQL vs ClickHouse 全面資料驗證
========================================
用途：驗證不同時間點和條件下 MSSQL 和 ClickHouse 的資料一致性
檢查項目：
1. 不同日期範圍的資料比較
2. 不同狀態的資料分布
3. V1 子類型分類一致性
4. 關鍵欄位的統計比較

使用方式：
- python scripts/verify_mssql_clickhouse_comprehensive.py
"""

import pymssql
import clickhouse_connect
from datetime import datetime, timedelta
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
    'host': '10.136.218.207',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}


def get_mssql_data_by_date(date_condition):
    """取得 MSSQL 指定日期條件的資料"""
    conn = pymssql.connect(**MSSQL_CONFIG)
    cursor = conn.cursor()
    
    cursor.execute(f"""
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
        WHERE {date_condition}
        ORDER BY hti.ID_
    """)
    
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_clickhouse_data_by_date(date_condition):
    """取得 ClickHouse 指定日期條件的資料"""
    client = clickhouse_connect.get_client(**CH_CONFIG)
    
    result = client.query(f"""
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
        WHERE {date_condition}
        ORDER BY task_id
    """)
    
    return result.result_rows


def analyze_vx_classification(mssql_data, ch_data, test_name):
    """分析 Vx 分類邏輯"""
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
    
    # 分析 V1 子類型
    v1_tasks = [tid for tid in common_tasks if mssql_dict[tid]['vx_type'] == 'V1']
    
    v1_npe_count = 0
    v1_mfg_count = 0
    
    for task_id in v1_tasks:
        factory = mssql_dict[task_id]['factory']
        if factory and 'NPE' in factory:
            v1_npe_count += 1
        else:
            v1_mfg_count += 1
    
    return {
        'test_name': test_name,
        'total_v1': len(v1_tasks),
        'v1_npe': v1_npe_count,
        'v1_mfg': v1_mfg_count,
        'common_tasks': len(common_tasks)
    }


def compare_data_summary(mssql_data, ch_data, test_name):
    """比較資料摘要"""
    # 1. 總筆數比較
    mssql_count = len(mssql_data)
    ch_count = len(ch_data)
    
    # 2. TaskId 比較
    mssql_task_ids = {row[0] for row in mssql_data}
    ch_task_ids = {row[0] for row in ch_data}
    
    only_in_mssql = mssql_task_ids - ch_task_ids
    only_in_ch = ch_task_ids - mssql_task_ids
    common_tasks = mssql_task_ids & ch_task_ids
    
    # 3. 狀態分布比較
    mssql_status_counts = {}
    for row in mssql_data:
        status = row[1]
        mssql_status_counts[status] = mssql_status_counts.get(status, 0) + 1
    
    ch_status_counts = {}
    for row in ch_data:
        status = row[1]
        ch_status_counts[status] = ch_status_counts.get(status, 0) + 1
    
    # 4. V1 分析
    v1_analysis = analyze_vx_classification(mssql_data, ch_data, test_name)
    
    # 計算一致性分數
    total_consistency = (
        1.0 if mssql_count == ch_count else max(0, 1 - abs(mssql_count - ch_count) / max(mssql_count, ch_count))
    )
    
    task_consistency = len(common_tasks) / max(len(mssql_task_ids), len(ch_task_ids)) if max(len(mssql_task_ids), len(ch_task_ids)) > 0 else 1.0
    
    return {
        'test_name': test_name,
        'mssql_count': mssql_count,
        'ch_count': ch_count,
        'common_tasks': len(common_tasks),
        'only_mssql': len(only_in_mssql),
        'only_ch': len(only_in_ch),
        'mssql_status': mssql_status_counts,
        'ch_status': ch_status_counts,
        'v1_analysis': v1_analysis,
        'total_consistency': total_consistency,
        'task_consistency': task_consistency,
        'overall_score': (total_consistency + task_consistency) / 2
    }


def run_comprehensive_tests():
    """執行全面測試"""
    logger.info("=" * 80)
    logger.info("MSSQL vs ClickHouse 全面資料驗證")
    logger.info("=" * 80)
    
    # 定義測試案例
    test_cases = [
        {
            'name': '最近7天',
            'mssql_condition': "CONVERT(DATE, hti.START_TIME_) >= DATEADD(day, -7, GETDATE())",
            'ch_condition': "task_create_date >= today() - 7"
        },
        {
            'name': '最近30天',
            'mssql_condition': "CONVERT(DATE, hti.START_TIME_) >= DATEADD(day, -30, GETDATE())",
            'ch_condition': "task_create_date >= today() - 30"
        },
        {
            'name': '2025年12月',
            'mssql_condition': "CONVERT(DATE, hti.START_TIME_) >= '2025-12-01' AND CONVERT(DATE, hti.START_TIME_) < '2026-01-01'",
            'ch_condition': "task_create_date >= '2025-12-01' AND task_create_date < '2026-01-01'"
        },
        {
            'name': '2026年1月前10天',
            'mssql_condition': "CONVERT(DATE, hti.START_TIME_) >= '2026-01-01' AND CONVERT(DATE, hti.START_TIME_) <= '2026-01-10'",
            'ch_condition': "task_create_date >= '2026-01-01' AND task_create_date <= '2026-01-10'"
        },
        {
            'name': '12月31日',
            'mssql_condition': "CONVERT(DATE, hti.START_TIME_) = '2025-12-31'",
            'ch_condition': "task_create_date = '2025-12-31'"
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        logger.info(f"\n執行測試: {test_case['name']}")
        
        try:
            # 取得資料
            mssql_data = get_mssql_data_by_date(test_case['mssql_condition'])
            ch_data = get_clickhouse_data_by_date(test_case['ch_condition'])
            
            logger.info(f"  MSSQL: {len(mssql_data):,} 筆")
            logger.info(f"  ClickHouse: {len(ch_data):,} 筆")
            
            # 比較資料
            result = compare_data_summary(mssql_data, ch_data, test_case['name'])
            results.append(result)
            
            # 顯示簡要結果
            logger.info(f"  一致性分數: {result['overall_score']:.2%}")
            
        except Exception as e:
            logger.error(f"  測試失敗: {e}")
            results.append({
                'test_name': test_case['name'],
                'error': str(e),
                'overall_score': 0.0
            })
    
    # 輸出詳細報告
    print_detailed_report(results)
    
    return results


def print_detailed_report(results):
    """輸出詳細報告"""
    logger.info("\n" + "=" * 80)
    logger.info("詳細驗證報告")
    logger.info("=" * 80)
    
    total_score = 0
    valid_tests = 0
    
    for result in results:
        if 'error' in result:
            logger.error(f"\n❌ {result['test_name']}: {result['error']}")
            continue
            
        valid_tests += 1
        total_score += result['overall_score']
        
        logger.info(f"\n📊 {result['test_name']}:")
        logger.info(f"  總筆數: MSSQL={result['mssql_count']:,}, ClickHouse={result['ch_count']:,}")
        logger.info(f"  共同任務: {result['common_tasks']:,}")
        logger.info(f"  差異: MSSQL獨有={result['only_mssql']:,}, ClickHouse獨有={result['only_ch']:,}")
        
        # 狀態分布
        logger.info("  狀態分布:")
        all_statuses = set(result['mssql_status'].keys()) | set(result['ch_status'].keys())
        for status in sorted(all_statuses):
            mssql_cnt = result['mssql_status'].get(status, 0)
            ch_cnt = result['ch_status'].get(status, 0)
            match = "✅" if mssql_cnt == ch_cnt else "❌"
            logger.info(f"    {status}: MSSQL={mssql_cnt:,}, ClickHouse={ch_cnt:,} {match}")
        
        # V1 分析
        v1 = result['v1_analysis']
        if v1['total_v1'] > 0:
            logger.info(f"  V1 子類型: NPE={v1['v1_npe']:,}, MFG={v1['v1_mfg']:,} (總計={v1['total_v1']:,})")
        
        # 一致性分數
        score_icon = "🎉" if result['overall_score'] >= 0.95 else "⚠️" if result['overall_score'] >= 0.90 else "❌"
        logger.info(f"  一致性分數: {result['overall_score']:.2%} {score_icon}")
    
    # 總結
    if valid_tests > 0:
        avg_score = total_score / valid_tests
        logger.info("\n" + "=" * 80)
        logger.info("總結")
        logger.info("=" * 80)
        logger.info(f"測試案例: {valid_tests} 個")
        logger.info(f"平均一致性: {avg_score:.2%}")
        
        if avg_score >= 0.95:
            logger.info("🎉 整體資料一致性優秀！")
        elif avg_score >= 0.90:
            logger.info("✅ 整體資料一致性良好")
        else:
            logger.warning("⚠️ 整體資料一致性需要改善")


def main():
    """主程式"""
    start_time = datetime.now()
    
    try:
        results = run_comprehensive_tests()
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"\n總耗時: {elapsed:.2f} 秒")
        
        return results
        
    except Exception as e:
        logger.error(f"驗證過程發生錯誤: {e}")
        return []


if __name__ == "__main__":
    main()