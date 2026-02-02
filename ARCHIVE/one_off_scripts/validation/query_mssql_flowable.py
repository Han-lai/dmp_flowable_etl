#!/usr/bin/env python3
"""
直接查詢 MSSQL FlowableTaskStats 表
確認原始資料結構和過濾邏輯
"""

import pymssql

MSSQL_CONFIG = {
    "server": "10.136.218.207",
    "port": 31433,
    "user": "sa",
    "password": "P@ssw0rd123",
    "database": "APP_SRV_COMMON"
}

def main():
    print("=" * 80)
    print("MSSQL FlowableTaskStats 表分析")
    print("=" * 80)
    
    conn = pymssql.connect(**MSSQL_CONFIG)
    cursor = conn.cursor()
    
    # 1. 總筆數
    cursor.execute("SELECT COUNT(*) FROM FlowableTaskStats")
    total = cursor.fetchone()[0]
    print(f"\n1. FlowableTaskStats 總筆數: {total:,}")
    
    # 2. 欄位結構
    print("\n2. 欄位結構:")
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'FlowableTaskStats'
        ORDER BY ORDINAL_POSITION
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]} ({row[1]})")
    
    # 3. TaskStatus 分布
    print("\n3. TaskStatus 分布:")
    cursor.execute("""
        SELECT TaskStatus, COUNT(*) as cnt
        FROM FlowableTaskStats
        GROUP BY TaskStatus
        ORDER BY cnt DESC
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]:,}")
    
    # 4. TaskBypass 分布
    print("\n4. TaskBypass 分布:")
    cursor.execute("""
        SELECT TaskBypass, COUNT(*) as cnt
        FROM FlowableTaskStats
        GROUP BY TaskBypass
        ORDER BY cnt DESC
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]:,}")
    
    # 5. Plant 分布
    print("\n5. Plant 分布:")
    cursor.execute("""
        SELECT Plant, COUNT(*) as cnt
        FROM FlowableTaskStats
        GROUP BY Plant
        ORDER BY cnt DESC
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]:,}")
    
    # 6. ProcessDefinitionKey 前綴分布
    print("\n6. ProcessDefinitionKey 前綴 (Vx) 分布:")
    cursor.execute("""
        SELECT 
            CASE 
                WHEN ProcessDefinitionKey LIKE 'V1%' THEN 'V1'
                WHEN ProcessDefinitionKey LIKE 'V2%' THEN 'V2'
                WHEN ProcessDefinitionKey LIKE 'V3%' THEN 'V3'
                ELSE 'Other'
            END as vx,
            COUNT(*) as cnt
        FROM FlowableTaskStats
        GROUP BY 
            CASE 
                WHEN ProcessDefinitionKey LIKE 'V1%' THEN 'V1'
                WHEN ProcessDefinitionKey LIKE 'V2%' THEN 'V2'
                WHEN ProcessDefinitionKey LIKE 'V3%' THEN 'V3'
                ELSE 'Other'
            END
        ORDER BY cnt DESC
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]:,}")
    
    # 7. 時間範圍
    print("\n7. 時間範圍:")
    cursor.execute("""
        SELECT 
            MIN(TaskCreateDate) as min_date,
            MAX(TaskCreateDate) as max_date
        FROM FlowableTaskStats
    """)
    row = cursor.fetchone()
    print(f"   TaskCreateDate: {row[0]} ~ {row[1]}")
    
    # 8. 樣本資料
    print("\n8. 樣本資料 (前 5 筆):")
    cursor.execute("""
        SELECT TOP 5 
            Plant, Factory, ProcessDefinitionKey, TaskDefinitionKey,
            TaskStatus, TaskBypass, MoNumber
        FROM FlowableTaskStats
        ORDER BY TaskCreateDate DESC
    """)
    for row in cursor.fetchall():
        print(f"   {row}")
    
    conn.close()
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
