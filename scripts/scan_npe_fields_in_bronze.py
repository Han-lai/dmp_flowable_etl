#!/usr/bin/env python3
"""
掃描 ClickHouse Bronze 層中含有 NPE 字眼的欄位
"""

import clickhouse_connect
from datetime import datetime

CLICKHOUSE_CONFIG = {
    'host': '10.136.218.207',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

def scan_npe_fields():
    """掃描 NPE 欄位"""
    print("\n" + "="*120)
    print("【掃描】ClickHouse Bronze 層中含有 NPE 字眼的欄位")
    print("="*120)
    
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_CONFIG['host'],
            port=CLICKHOUSE_CONFIG['port'],
            username=CLICKHOUSE_CONFIG['username'],
            password=CLICKHOUSE_CONFIG['password']
        )
        
        # 列出 Bronze 層所有表
        print("\n【步驟 1】列出 Bronze 層所有表")
        print("-" * 120)
        
        sql_tables = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'bronze'
        ORDER BY table_name
        """
        
        result = client.query(sql_tables)
        tables = [row[0] for row in result.result_rows]
        print(f"找到 {len(tables)} 張表：")
        for table in tables:
            print(f"  - {table}")
        
        # 對每張表掃描是否有 NPE 字眼
        print("\n【步驟 2】掃描各表中是否含有 NPE 字眼")
        print("-" * 120)
        
        npe_findings = {}
        
        for table in tables:
            try:
                # 取得表的欄位資訊
                sql_columns = f"""
                SELECT name, type 
                FROM system.columns 
                WHERE database = 'bronze' AND table = '{table}'
                ORDER BY name
                """
                
                result = client.query(sql_columns)
                columns = [(row[0], row[1]) for row in result.result_rows]
                
                # 對每個欄位掃描是否含有 NPE
                for col_name, col_type in columns:
                    try:
                        # 只掃描字串類型的欄位
                        if 'String' in col_type or 'JSON' in col_type:
                            sql_scan = f"""
                            SELECT COUNT(*) as npe_count
                            FROM bronze.{table}
                            WHERE {col_name} LIKE '%NPE%'
                            LIMIT 1
                            """
                            
                            result = client.query(sql_scan)
                            npe_count = result.result_rows[0][0] if result.result_rows else 0
                            
                            if npe_count > 0:
                                key = f"{table}.{col_name}"
                                npe_findings[key] = npe_count
                                print(f"✅ {table}.{col_name} ({col_type}): {npe_count} 筆含有 NPE")
                    except Exception as e:
                        pass
            except Exception as e:
                print(f"⚠️ 掃描表 {table} 失敗：{str(e)}")
        
        # 總結
        print("\n【步驟 3】掃描結果總結")
        print("-" * 120)
        
        if npe_findings:
            print(f"✅ 找到 {len(npe_findings)} 個含有 NPE 字眼的欄位：")
            for field, count in sorted(npe_findings.items(), key=lambda x: x[1], reverse=True):
                print(f"  {field}: {count} 筆")
        else:
            print("❌ 未找到含有 NPE 字眼的欄位")
        
        # 詳細檢查 WJ2+NBU+E5+2025-12-31 的任務
        print("\n【步驟 4】詳細檢查 WJ2+NBU+E5+2025-12-31 的任務中哪個欄位含有 NPE")
        print("-" * 120)
        
        # 檢查 common_flowable_task_stats 表
        sql_check = """
        SELECT 
            t.TaskId,
            t.Plant,
            t.Factory,
            t.Line,
            t.TaskDefinitionKey,
            COALESCE(v.varinst_moNumber, t.MoNumber) AS mo_number,
            p.BUSINESS_KEY_,
            p.NAME_
        FROM bronze.common_flowable_task_stats t
        LEFT JOIN bronze.bpm_act_hi_procinst p 
            ON t.ProcessInstanceId = p.PROC_INST_ID_
        LEFT JOIN silver.mv_varinst_pivoted v
            ON t.ProcessInstanceId = v.PROC_INST_ID_
        WHERE t.Plant = 'WJ2' 
          AND t.Factory = 'NBU' 
          AND t.Line = 'E5'
          AND toDate(t.TaskCreateDate) = '2025-12-31'
          AND t.TaskId IS NOT NULL 
          AND t.TaskId != ''
        LIMIT 1
        """
        
        result = client.query(sql_check)
        if result.result_rows:
            row = result.result_rows[0]
            print(f"任務 ID: {row[0]}")
            print(f"Plant: {row[1]}")
            print(f"Factory: {row[2]}")
            print(f"Line: {row[3]}")
            print(f"TaskDefinitionKey: {row[4]}")
            print(f"MoNumber: {row[5]}")
            print(f"BUSINESS_KEY_: {row[6]}")
            print(f"NAME_: {row[7]}")
            
            # 檢查各欄位是否含有 NPE
            print("\n【檢查各欄位是否含有 NPE】")
            fields_to_check = {
                'Factory': row[2],
                'BUSINESS_KEY_': row[6],
                'NAME_': row[7]
            }
            
            for field_name, field_value in fields_to_check.items():
                if field_value and 'NPE' in str(field_value):
                    print(f"  ✅ {field_name} 含有 NPE: {field_value}")
                else:
                    print(f"  ❌ {field_name} 不含 NPE: {field_value}")
        
        print("\n" + "="*120)
        
    except Exception as e:
        print(f"\n❌ 掃描失敗：{str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    scan_npe_fields()
