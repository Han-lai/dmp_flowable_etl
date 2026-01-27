#!/usr/bin/env python3
"""
重建 MVIEW 並驗證 V1_NPE 邏輯（使用 bpm_act_hi_varinst.NAME_ 欄位判別 NPE）
"""

import clickhouse_connect
from datetime import datetime

CLICKHOUSE_CONFIG = {
    'host': '10.136.218.207',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

def rebuild_and_verify():
    """重建 MVIEW 並驗證"""
    print("\n" + "="*120)
    print("【重建 MVIEW】使用 bpm_act_hi_varinst.NAME_ 欄位判別 NPE")
    print("="*120)
    
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_CONFIG['host'],
            port=CLICKHOUSE_CONFIG['port'],
            username=CLICKHOUSE_CONFIG['username'],
            password=CLICKHOUSE_CONFIG['password']
        )
        
        # 讀取 SQL 檔案
        print("\n【步驟 1】讀取 SQL 檔案")
        print("-" * 120)
        
        with open('D:\\kiro\\dmp_flowable\\sql\\11_create_silver_mviews_layer1.sql', 'r', encoding='utf-8') as f:
            sql_layer1 = f.read()
        
        with open('D:\\kiro\\dmp_flowable\\sql\\12_create_silver_mviews_layer2.sql', 'r', encoding='utf-8') as f:
            sql_layer2 = f.read()
        
        print("✅ SQL 檔案已讀取")
        
        # 執行 Layer 1 SQL
        print("\n【步驟 2】執行 Layer 1 SQL 重建第一層 MVIEW")
        print("-" * 120)
        
        statements = [s.strip() for s in sql_layer1.split(';') if s.strip()]
        
        for i, stmt in enumerate(statements, 1):
            try:
                print(f"執行語句 {i}/{len(statements)}...", end=' ')
                client.command(stmt)
                print("✅")
            except Exception as e:
                if 'already exists' in str(e) or 'ALREADY_EXISTS' in str(e):
                    print("⚠️ (已存在，跳過)")
                else:
                    print(f"❌ {str(e)[:80]}")
        
        # 執行 Layer 2 SQL
        print("\n【步驟 3】執行 Layer 2 SQL 重建第二層 MVIEW")
        print("-" * 120)
        
        statements = [s.strip() for s in sql_layer2.split(';') if s.strip()]
        
        for i, stmt in enumerate(statements, 1):
            if stmt.startswith('SELECT') and 'status' in stmt.lower():
                continue
            
            try:
                print(f"執行語句 {i}/{len(statements)}...", end=' ')
                client.command(stmt)
                print("✅")
            except Exception as e:
                if 'already exists' in str(e) or 'ALREADY_EXISTS' in str(e):
                    print("⚠️ (已存在，跳過)")
                else:
                    print(f"❌ {str(e)[:80]}")
        
        # 驗證 WJ2+NBU+E5+2025-12-31 的任務
        print("\n【步驟 4】驗證 WJ2+NBU+E5+2025-12-31 的任務")
        print("-" * 120)
        
        sql_verify = """
        SELECT 
            vx_type,
            vx_subtype,
            COUNT(*) AS task_count
        FROM silver.mv_fact_task_vx_attribution
        WHERE plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND task_create_date = '2025-12-31'
          AND is_excluded = 0
        GROUP BY vx_type, vx_subtype
        ORDER BY vx_type, vx_subtype
        """
        
        result = client.query(sql_verify)
        rows = result.result_rows
        
        print(f"{'Vx Type':<15} {'Vx Subtype':<15} {'Count':<10}")
        print("-" * 120)
        
        total = 0
        for vx_type, vx_subtype, count in rows:
            print(f"{str(vx_type):<15} {str(vx_subtype):<15} {count:<10}")
            total += count
        
        print("-" * 120)
        print(f"{'總計':<15} {'':<15} {total:<10}")
        
        # 詳細檢查 V1_NPE 任務
        print("\n【步驟 5】詳細檢查 V1_NPE 任務")
        print("-" * 120)
        
        sql_v1_npe = """
        SELECT 
            task_id,
            task_definition_key,
            mo_number,
            task_status,
            COUNT(*) AS count
        FROM silver.mv_fact_task_vx_attribution
        WHERE plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND task_create_date = '2025-12-31'
          AND vx_subtype = 'V1_NPE'
          AND is_excluded = 0
        GROUP BY task_id, task_definition_key, mo_number, task_status
        ORDER BY task_status
        LIMIT 20
        """
        
        result = client.query(sql_v1_npe)
        rows = result.result_rows
        
        if len(rows) == 0:
            print("❌ 沒有找到 V1_NPE 任務")
        else:
            print(f"✅ 找到 {len(rows)} 個 V1_NPE 任務（顯示前 20 筆）：")
            print(f"{'Task ID':<40} {'TaskDefKey':<20} {'MoNumber':<15} {'Status':<10}")
            print("-" * 120)
            
            for task_id, task_def_key, mo_number, task_status, count in rows:
                print(f"{str(task_id):<40} {str(task_def_key):<20} {str(mo_number):<15} {str(task_status):<10}")
        
        # 檢查 varinst_name 中含有 NPE 的任務
        print("\n【步驟 6】檢查 varinst_name 中含有 NPE 的任務")
        print("-" * 120)
        
        sql_varinst_npe = """
        SELECT 
            COUNT(*) AS task_count
        FROM silver.mv_fact_task_vx_attribution t
        LEFT JOIN silver.mv_varinst_pivoted v
            ON t.proc_inst_id = v.PROC_INST_ID_
        WHERE t.plant = 'WJ2' 
          AND t.factory = 'NBU' 
          AND t.line = 'E5'
          AND t.task_create_date = '2025-12-31'
          AND t.is_excluded = 0
          AND v.varinst_name LIKE '%NPE%'
        """
        
        result = client.query(sql_varinst_npe)
        rows = result.result_rows
        
        if rows and rows[0][0] > 0:
            print(f"✅ 找到 {rows[0][0]} 個 varinst_name 含有 NPE 的任務")
        else:
            print("❌ 沒有找到 varinst_name 含有 NPE 的任務")
        
        print("\n" + "="*120)
        
    except Exception as e:
        print(f"\n❌ 重建失敗：{str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    rebuild_and_verify()
