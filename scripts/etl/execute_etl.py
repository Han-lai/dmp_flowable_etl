"""
資料流重建執行腳本
依序執行 SQL 檔案來重建 Bronze/Silver/Gold 架構
"""
import clickhouse_connect
import os
import sys
from pathlib import Path

# ClickHouse 連線設定 (優先使用環境變數)
CH_CONFIG = {
    'host': os.getenv('CLICKHOUSE_HOST', '10.136.218.207'),
    'port': int(os.getenv('CLICKHOUSE_PORT', '8121')),
    'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
    'password': os.getenv('CLICKHOUSE_PASSWORD', 'default'),
    'database': os.getenv('CLICKHOUSE_DATABASE', 'default')
}

# SQL 檔案執行順序
# SQL 檔案執行順序
SQL_FILES = [
    ('01_bronze_flowable_core.sql', 'Bronze Layer 1 (Flowable 核心表)'),
    ('02_bronze_common_dims.sql', 'Bronze Layer 2 (Common Dimensions)'),
    ('03_silver_pivot_and_hierarchy.sql', 'Silver Layer 1 (Pivot + 五階維度)'),
    ('04_silver_fact_tasks.sql', 'Silver Layer 2 (核心事實表)'),
    ('05_silver_dim_users.sql', 'Silver Layer 3 (User Dimension)'),
    ('06_gold_kpi_task_completion.sql', 'Gold Layer 1 (L5 任務完成率)'),
    ('07_gold_kpi_user_utilization.sql', 'Gold Layer 2 (L7 人員使用率)'),
]

def get_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(**CH_CONFIG)

def execute_sql_file(client, sql_file: Path, description: str):
    """執行單一 SQL 檔案 (附帶安全檢查)"""
    print(f"\n{'-'*60}")
    print(f"準備執行: {sql_file.name}")
    print(f"說明: {description}")
    
    sql_content = sql_file.read_text(encoding='utf-8')
    
    # 1. 解析目標表 (簡單 Regex)
    import re
    # 匹配 CREATE TABLE/VIEW/MATERIALIZED VIEW db.table
    pattern = re.compile(r'CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW|MATERIALIZED\s+VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_.]+)', re.IGNORECASE)
    tables = pattern.findall(sql_content)
    
    # 2. 檢查表是否存在與資料量
    existing_tables = []
    for table in tables:
        try:
            # 檢查是否存在
            check_sql = f"EXISTS TABLE {table}"
            exists = client.command(check_sql)
            if exists:
                # 檢查資料量
                count = client.command(f"SELECT count() FROM {table}")
                existing_tables.append((table, count))
        except Exception:
            pass # 忽略檢查錯誤
            
    # 3. 若表存在，詢問使用者
    if existing_tables:
        print(f"\n⚠️  警告: 此腳本將重建以下已存在的表 (包含 DROP TABLE):")
        for table, count in existing_tables:
            print(f"   - {table}: {count:,} rows")
        
        response = input("\n是否繼續執行重建? (y/N): ").lower().strip()
        if response != 'y':
            print(f"⛔ 已跳過: {sql_file.name}")
            return

    print('-'*60)
    
    # 分割成多個語句（以分號分隔，忽略註解中的分號）
    statements = []
    current = []
    for line in sql_content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('--'):
            continue
        current.append(line)
        if stripped.endswith(';'):
            stmt = '\n'.join(current).strip()
            if stmt and stmt != ';':
                statements.append(stmt)
            current = []
    
    # 執行每個語句
    for i, stmt in enumerate(statements, 1):
        if not stmt.strip():
            continue
        try:
            # 檢查是否是 SELECT 語句
            if stmt.strip().upper().startswith('SELECT'):
                # 略過 SELECT 輸出以免洗版 (或可保留)
                pass 
            else:
                client.command(stmt)
                # 簡化輸出
                # print(f"[{i}/{len(statements)}] ✓ 語句執行成功")
        except Exception as e:
            print(f"[{i}/{len(statements)}] ✗ 錯誤: {e}")
            # 繼續執行下一個語句
            continue
    
    print(f"✓ {sql_file.name} 執行完成")

def main():
    """主程式"""
    print("="*60)
    print("資料流重建執行腳本")
    print("="*60)
    
    # 取得 SQL 目錄 - 使用絕對路徑
    sql_dir = Path(r'D:\kiro\dmp_flowable\sql\etl')
    
    if not sql_dir.exists():
        print(f"錯誤: SQL 目錄不存在: {sql_dir}")
        sys.exit(1)
    
    print(f"SQL 目錄: {sql_dir}")
    print(f"ClickHouse: {CH_CONFIG['host']}:{CH_CONFIG['port']}")
    
    # 連線測試
    try:
        client = get_client()
        result = client.query("SELECT 1")
        print("✓ ClickHouse 連線成功")
    except Exception as e:
        print(f"✗ ClickHouse 連線失敗: {e}")
        sys.exit(1)
    
    # 依序執行 SQL 檔案
    for sql_file_name, description in SQL_FILES:
        sql_file = sql_dir / sql_file_name
        if sql_file.exists():
            execute_sql_file(client, sql_file, description)
        else:
            print(f"⚠ 跳過: {sql_file_name} (檔案不存在)")
    
    print("\n" + "="*60)
    print("✓ 資料流重建完成！")
    print("="*60)
    print("\n下一步:")
    print("1. 執行 06_validation.sql 驗證資料")
    print("2. 確認無誤後執行 05_cleanup_path_a.sql 清理舊表")

if __name__ == '__main__':
    main()
