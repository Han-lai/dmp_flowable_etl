"""
資料流重建執行腳本 (安全版)
只重建 Silver 和 Gold 層，保留 Bronze 層原始資料
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

# SQL 檔案執行順序 (排除 Bronze 層)
SQL_FILES = [
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
    
    # 分割成多個語句
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
            # 檢查是否是 SELECT 語句 (用於驗證)
            if stmt.strip().upper().startswith('SELECT'):
                print(f"   執行驗證查詢: {stmt[:50]}...")
                result = client.query(stmt)
                # 簡單列印結果 (取第一列或統計值)
                if result.result_rows:
                    print(f"   => 結果: {result.result_rows}")
                else:
                    print(f"   => 結果: (無資料)")
            else:
                client.command(stmt)
        except Exception as e:
            print(f"[{i}/{len(statements)}] ✗ 錯誤: {e}")
            if "UNKNOWN_TABLE" in str(e):
                continue # 忽略 Drop table 不存在的錯誤
            raise e
    
    print(f"✓ {sql_file.name} 執行完成")

def main():
    """主程式"""
    print("="*60)
    print("資料流重建執行腳本 (安全版 - 保留 Bronze 資料)")
    print("="*60)
    
    # 取得 SQL 目錄
    sql_dir = Path(r'D:\kiro\dmp_flowable\sql\rebuild')
    
    if not sql_dir.exists():
        print(f"錯誤: SQL 目錄不存在: {sql_dir}")
        sys.exit(1)
    
    print(f"SQL 目錄: {sql_dir}")
    
    # 連線測試
    try:
        client = get_client()
        result = client.query("SELECT 1")
        print("✓ ClickHouse 連線成功")
    except Exception as e:
        print(f"✗ ClickHouse 連線失敗: {e}")
        sys.exit(1)
    
    print("\n⚠️  注意: 此腳本將重建 Silver 和 Gold 層的 Materialized Views。")
    print("Bronze 層的原始資料 (bpm_act_hi_*, common_*) 將會被保留。")
    
    response = input("\n是否繼續執行? (y/N): ").lower().strip()
    if response != 'y':
        print("⛔ 已取消")
        sys.exit(0)

    # 依序執行 SQL 檔案
    for sql_file_name, description in SQL_FILES:
        sql_file = sql_dir / sql_file_name
        if sql_file.exists():
            execute_sql_file(client, sql_file, description)
            import time
            time.sleep(2) # 等待 MView 刷新生效
        else:
            print(f"⚠ 跳過: {sql_file_name} (檔案不存在)")
    
    print("\n" + "="*60)
    print("✓ MView 重建完成！(48小時更新設定已生效)")
    print("="*60)

if __name__ == '__main__':
    main()
