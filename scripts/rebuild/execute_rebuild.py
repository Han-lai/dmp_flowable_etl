"""
資料流重建執行腳本
依序執行 SQL 檔案來重建 Bronze/Silver/Gold 架構
"""
import clickhouse_connect
import os
import sys
from pathlib import Path

# ClickHouse 連線設定
CH_CONFIG = {
    'host': 'REDACTED_IP',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

# SQL 檔案執行順序
SQL_FILES = [
    ('01_bronze_add_ttl.sql', 'Bronze TTL 設定'),
    ('02_silver_layer1.sql', 'Silver Layer 1 (VARINST + 五階維度)'),
    ('03_silver_layer2.sql', 'Silver Layer 2 (核心事實表)'),
    ('04_gold_refreshable.sql', 'Gold REFRESHABLE MView'),
]

def get_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(**CH_CONFIG)

def execute_sql_file(client, sql_file: Path, description: str):
    """執行單一 SQL 檔案"""
    print(f"\n{'='*60}")
    print(f"執行: {sql_file.name}")
    print(f"說明: {description}")
    print('='*60)
    
    sql_content = sql_file.read_text(encoding='utf-8')
    
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
                result = client.query(stmt)
                if result.result_rows:
                    print(f"\n[{i}/{len(statements)}] 查詢結果:")
                    # 印出欄位名稱
                    print("  " + " | ".join(str(c) for c in result.column_names))
                    print("  " + "-" * 50)
                    for row in result.result_rows[:10]:  # 最多顯示 10 筆
                        print("  " + " | ".join(str(v) for v in row))
            else:
                client.command(stmt)
                print(f"[{i}/{len(statements)}] ✓ 執行成功")
        except Exception as e:
            print(f"[{i}/{len(statements)}] ✗ 錯誤: {e}")
            # 繼續執行下一個語句
            continue
    
    print(f"\n✓ {sql_file.name} 執行完成")

def main():
    """主程式"""
    print("="*60)
    print("資料流重建執行腳本")
    print("="*60)
    
    # 取得 SQL 目錄 - 使用絕對路徑
    sql_dir = Path(r'D:\kiro\dmp_flowable\sql\rebuild')
    
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
