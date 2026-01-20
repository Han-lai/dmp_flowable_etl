#!/usr/bin/env python3
"""
Gold 層快照缺日監控解決方案
提供最小且穩定的排程和監控機制
"""
import clickhouse_connect
from datetime import datetime, timedelta
import sys
import os

# ClickHouse 連接設定
CH_HOST = "REDACTED_IP"
CH_PORT = 8121
CH_USER = "default"
CH_PASSWORD = "default"

def get_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD
    )

def check_missing_snapshots(days_back=7):
    """檢查缺失的快照日期"""
    client = get_client()
    
    # 生成預期的日期範圍
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days_back)
    
    expected_dates = []
    current_date = start_date
    while current_date <= end_date:
        expected_dates.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)
    
    # 查詢實際存在的日期
    sql = f"""
    SELECT DISTINCT snapshot_date
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    WHERE snapshot_date >= '{start_date}' AND snapshot_date <= '{end_date}'
    ORDER BY snapshot_date
    """
    
    result = client.query(sql)
    existing_dates = [str(row[0]) for row in result.result_rows]
    
    # 找出缺失的日期
    missing_dates = [date for date in expected_dates if date not in existing_dates]
    
    return missing_dates, existing_dates

def create_snapshot_for_date(date_str):
    """為指定日期建立快照"""
    script_path = os.path.join(os.path.dirname(__file__), 'create_gold_snapshot.py')
    
    if not os.path.exists(script_path):
        print(f"❌ 快照腳本不存在: {script_path}")
        return False
    
    try:
        import subprocess
        result = subprocess.run([
            sys.executable, script_path, '--date', date_str
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"✅ {date_str}: 快照建立成功")
            return True
        else:
            print(f"❌ {date_str}: 快照建立失敗")
            print(f"   錯誤: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ {date_str}: 執行失敗 - {e}")
        return False

def main():
    """主要監控和修復流程"""
    print("=" * 60)
    print("Gold 層快照缺日監控")
    print("=" * 60)
    
    # 檢查缺失的快照
    missing_dates, existing_dates = check_missing_snapshots(days_back=7)
    
    print(f"📊 最近 7 天快照狀況:")
    print(f"   存在日期: {len(existing_dates)} 天")
    print(f"   缺失日期: {len(missing_dates)} 天")
    
    if existing_dates:
        print(f"   最新快照: {max(existing_dates)}")
    
    if missing_dates:
        print(f"\n❌ 缺失的日期:")
        for date in missing_dates:
            print(f"   {date}")
        
        # 詢問是否自動修復
        if len(sys.argv) > 1 and sys.argv[1] == '--auto-fix':
            print(f"\n🔧 自動修復缺失的快照...")
            success_count = 0
            for date in missing_dates:
                if create_snapshot_for_date(date):
                    success_count += 1
            
            print(f"\n📊 修復結果: {success_count}/{len(missing_dates)} 成功")
        else:
            print(f"\n💡 執行修復: python {__file__} --auto-fix")
    else:
        print(f"\n✅ 所有日期的快照都存在")
    
    # 檢查今天是否需要建立快照
    today = datetime.now().strftime('%Y-%m-%d')
    if today in missing_dates:
        print(f"\n⚠️ 今天 ({today}) 的快照尚未建立")
        print(f"   建議立即執行: python scripts/create_gold_snapshot.py")

if __name__ == "__main__":
    main()