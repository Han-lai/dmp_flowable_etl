#!/usr/bin/env python3
"""
在 MSSQL 中查找包含 NPE 字眼的欄位
"""

import pyodbc
from datetime import datetime

MSSQL_CONFIG = {
    'server': 'REDACTED_IP',
    'database': 'APP_SRV_BPM',
    'username': 'sa',
    'password': 'P@ssw0rd'
}

def find_npe_fields():
    """查找包含 NPE 的欄位"""
    print("\n" + "="*120)
    print("【查詢】MSSQL 中包含 NPE 字眼的欄位")
    print("="*120)
    
    try:
        # 連接 MSSQL
        conn_str = f"Driver={{ODBC Driver 17 for SQL Server}};Server={MSSQL_CONFIG['server']};Database={MSSQL_CONFIG['database']};UID={MSSQL_CONFIG['username']};PWD={MSSQL_CONFIG['password']}"
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # 查詢相關表的欄位
        tables_to_check = [
            ('ACT_HI_PROCINST', ['BUSINESS_KEY_', 'NAME_']),
            ('ACT_HI_VARINST', ['TEXT_', 'NAME_']),
            ('ACT_HI_TASKINST', ['NAME_']),
            ('FlowableTaskStats', ['MoNumber', 'Plant', 'Factory', 'Line']),
        ]
        
        for table_name, columns in tables_to_check:
            print(f"\n【檢查表】{table_name}")
            print("-" * 120)
            
            for col_name in columns:
                # 檢查該欄位是否存在
                check_sql = f"""
                SELECT COUNT(*) as col_count
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = '{table_name}' AND COLUMN_NAME = '{col_name}'
                """
                
                try:
                    cursor.execute(check_sql)
                    result = cursor.fetchone()
                    
                    if result[0] == 0:
                        print(f"  ❌ 欄位 {col_name} 不存在")
                        continue
                    
                    # 查詢包含 NPE 的記錄
                    query_sql = f"""
                    SELECT TOP 10 {col_name}
                    FROM {table_name}
                    WHERE {col_name} LIKE '%NPE%'
                    """
                    
                    cursor.execute(query_sql)
                    rows = cursor.fetchall()
                    
                    if len(rows) > 0:
                        print(f"  ✅ 欄位 {col_name} 包含 NPE（找到 {len(rows)} 筆示例）：")
                        for row in rows:
                            print(f"     - {row[0]}")
                    else:
                        print(f"  ❌ 欄位 {col_name} 不包含 NPE")
                
                except Exception as e:
                    print(f"  ⚠️ 查詢欄位 {col_name} 失敗：{str(e)}")
        
        # 特別查詢 FlowableTaskStats 中 WJ2+NBU+E5+2025-12-31 的任務
        print("\n【特別查詢】FlowableTaskStats 中 WJ2+NBU+E5+2025-12-31 的任務")
        print("-" * 120)
        
        sql = """
        SELECT TOP 5 
            MoNumber,
            Plant,
            Factory,
            Line,
            TaskDefinitionKey
        FROM FlowableTaskStats
        WHERE Plant = 'WJ2' 
          AND Factory = 'NBU' 
          AND Line = 'E5'
          AND CAST(TaskCreateDate AS DATE) = '2025-12-31'
        """
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        print(f"找到 {len(rows)} 筆任務：")
        for row in rows:
            print(f"  MoNumber: {row[0]}, Plant: {row[1]}, Factory: {row[2]}, Line: {row[3]}, TaskDefKey: {row[4]}")
        
        # 查詢 ACT_HI_PROCINST 中對應的 BUSINESS_KEY_
        print("\n【查詢】ACT_HI_PROCINST 中對應的 BUSINESS_KEY_")
        print("-" * 120)
        
        sql = """
        SELECT TOP 5 
            p.BUSINESS_KEY_,
            t.MoNumber,
            t.Plant,
            t.Factory
        FROM FlowableTaskStats t
        LEFT JOIN ACT_HI_PROCINST p ON t.ProcessInstanceId = p.PROC_INST_ID_
        WHERE t.Plant = 'WJ2' 
          AND t.Factory = 'NBU' 
          AND t.Line = 'E5'
          AND CAST(t.TaskCreateDate AS DATE) = '2025-12-31'
        """
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        print(f"找到 {len(rows)} 筆任務的 BUSINESS_KEY_：")
        for row in rows:
            print(f"  BUSINESS_KEY_: {row[0]}, MoNumber: {row[1]}, Plant: {row[2]}, Factory: {row[3]}")
        
        # 查詢 ACT_HI_VARINST 中的 factory 變數
        print("\n【查詢】ACT_HI_VARINST 中的 factory 變數")
        print("-" * 120)
        
        sql = """
        SELECT TOP 10 
            v.TEXT_ as factory_value,
            COUNT(*) as count
        FROM ACT_HI_VARINST v
        WHERE v.NAME_ = 'factory'
          AND v.TEXT_ LIKE '%NPE%'
        GROUP BY v.TEXT_
        """
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        if len(rows) > 0:
            print(f"✅ 找到包含 NPE 的 factory 變數：")
            for row in rows:
                print(f"  {row[0]}: {row[1]} 筆")
        else:
            print("❌ 沒有找到包含 NPE 的 factory 變數")
        
        conn.close()
        print("\n" + "="*120)
        
    except Exception as e:
        print(f"\n❌ 查詢失敗：{str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    find_npe_fields()
