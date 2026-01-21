#!/usr/bin/env python3
"""
重建 MVIEW 並驗證 V1_NPE 邏輯（使用 Factory 欄位判別 NPE）
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
    print("【重建 MVIEW】使用 Factory 欄位判別 NPE")
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
        
        with open('D:\\kiro\\dmp_flowable\\sql\\12_create_silver_mviews_layer2.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        print("✅ SQL 檔案已讀取")
        
        # 執行 SQL 重建 MVIEW
        print("\n【步驟 2】執行 SQL 重建 MVIEW")
        print("-" * 120)
        
        # 分割 SQL 語句
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        
        for i, stmt in enumerate(statements, 1):
            if stmt.startswith('SELECT') and 'status' in stmt.lower():
                # 跳過最後的 SELECT 語句
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
        print("\n【步驟 3】驗證 WJ2+NBU+E5+2025-12-31 的任務")
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
        print("\n【步驟 4】詳細檢查 V1_NPE 任務")
        print("-" * 120)
        
        sql_v1_npe = """
        SELECT 
            task_id,
            task_definition_key,
            mo_number,
            factory,
            task_status,
            COUNT(*) AS count
        FROM silver.mv_fact_task_vx_attribution
        WHERE plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND task_create_date = '2025-12-31'
          AND vx_subtype = 'V1_NPE'
          AND is_excluded = 0
        GROUP BY task_id, task_definition_key, mo_number, factory, task_status
        ORDER BY task_status
        """
        
        result = client.query(sql_v1_npe)
        rows = result.result_rows
        
        if len(rows) == 0:
            print("❌ 沒有找到 V1_NPE 任務")
        else:
            print(f"✅ 找到 {len(rows)} 個 V1_NPE 任務：")
            print(f"{'Task ID':<40} {'TaskDefKey':<20} {'MoNumber':<15} {'Factory':<10} {'Status':<10}")
            print("-" * 120)
            
            for task_id, task_def_key, mo_number, factory, task_status, count in rows:
                print(f"{str(task_id):<40} {str(task_def_key):<20} {str(mo_number):<15} {str(factory):<10} {str(task_status):<10}")
        
        # 檢查 Factory 欄位中含有 NPE 的任務
        print("\n【步驟 5】檢查 Factory 欄位中含有 NPE 的任務")
        print("-" * 120)
        
        sql_factory_npe = """
        SELECT 
            DISTINCT factory,
            COUNT(*) AS task_count
        FROM silver.mv_fact_task_vx_attribution
        WHERE plant = 'WJ2' 
          AND line = 'E5'
          AND task_create_date = '2025-12-31'
          AND factory LIKE '%NPE%'
          AND is_excluded = 0
        GROUP BY factory
        ORDER BY factory
        """
        
        result = client.query(sql_factory_npe)
        rows = result.result_rows
        
        if len(rows) == 0:
            print("❌ 沒有找到 Factory 含有 NPE 的任務")
        else:
            print(f"✅ 找到 {len(rows)} 個 Factory 含有 NPE 的任務：")
            for factory, count in rows:
                print(f"  {factory}: {count} 筆")
        
        print("\n" + "="*120)
        
    except Exception as e:
        print(f"\n❌ 重建失敗：{str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    rebuild_and_verify()
