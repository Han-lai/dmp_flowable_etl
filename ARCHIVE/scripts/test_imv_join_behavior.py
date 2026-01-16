"""
測試 ClickHouse 增量 MView (TO <table>) 的 JOIN 行為

驗證項目：
1. 主表 INSERT 時，MView 是否觸發
2. JOIN 表 INSERT 時，MView 是否觸發
3. JOIN 表 UPDATE 時，已寫入的資料是否更新
"""

import clickhouse_connect
import time

# ClickHouse 連線
client = clickhouse_connect.get_client(
    host='10.136.218.207',
    port=8121,
    username='default',
    password='default'
)

def setup_test_tables():
    """建立測試用的表和 MView"""
    print("=" * 60)
    print("Step 1: 建立測試表")
    print("=" * 60)
    
    # 清理舊的測試物件
    client.command("DROP TABLE IF EXISTS test.imv_target")
    client.command("DROP VIEW IF EXISTS test.imv_join_test")
    client.command("DROP TABLE IF EXISTS test.main_table")
    client.command("DROP TABLE IF EXISTS test.lookup_table")
    client.command("CREATE DATABASE IF NOT EXISTS test")
    
    # 主表 (會被監控)
    client.command("""
        CREATE TABLE test.main_table (
            id UInt32,
            name String,
            lookup_id UInt32,
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY id
    """)
    print("✅ 建立 test.main_table (主表)")
    
    # Lookup 表 (JOIN 用)
    client.command("""
        CREATE TABLE test.lookup_table (
            id UInt32,
            category String
        ) ENGINE = MergeTree()
        ORDER BY id
    """)
    print("✅ 建立 test.lookup_table (Lookup 表)")
    
    # Target 表 (MView 輸出)
    client.command("""
        CREATE TABLE test.imv_target (
            id UInt32,
            name String,
            category String,
            created_at DateTime
        ) ENGINE = MergeTree()
        ORDER BY id
    """)
    print("✅ 建立 test.imv_target (Target 表)")
    
    # 增量 MView with JOIN
    client.command("""
        CREATE MATERIALIZED VIEW test.imv_join_test
        TO test.imv_target
        AS
        SELECT 
            m.id,
            m.name,
            l.category,
            m.created_at
        FROM test.main_table AS m
        LEFT JOIN test.lookup_table AS l ON m.lookup_id = l.id
    """)
    print("✅ 建立 test.imv_join_test (增量 MView with JOIN)")


def test_scenario_1():
    """測試 1: 先有 Lookup 資料，再 INSERT 主表"""
    print("\n" + "=" * 60)
    print("Test 1: 先有 Lookup 資料，再 INSERT 主表")
    print("=" * 60)
    
    # 先插入 Lookup 資料
    client.command("INSERT INTO test.lookup_table VALUES (1, 'Category_A')")
    print("📥 INSERT lookup_table: id=1, category='Category_A'")
    
    # 再插入主表
    client.command("INSERT INTO test.main_table (id, name, lookup_id) VALUES (1, 'Item_1', 1)")
    print("📥 INSERT main_table: id=1, name='Item_1', lookup_id=1")
    
    time.sleep(1)  # 等待 MView 處理
    
    # 查詢結果
    result = client.query("SELECT * FROM test.imv_target WHERE id = 1")
    print(f"\n📊 Target 表結果:")
    for row in result.result_rows:
        print(f"   id={row[0]}, name={row[1]}, category={row[2]}")
    
    if result.result_rows and result.result_rows[0][2] == 'Category_A':
        print("✅ 結果正確: JOIN 成功取得 category")
    else:
        print("❌ 結果異常")


def test_scenario_2():
    """測試 2: 主表 INSERT 時，Lookup 表還沒有對應資料"""
    print("\n" + "=" * 60)
    print("Test 2: 主表 INSERT 時，Lookup 表還沒有對應資料")
    print("=" * 60)
    
    # 先插入主表 (lookup_id=2 還不存在)
    client.command("INSERT INTO test.main_table (id, name, lookup_id) VALUES (2, 'Item_2', 2)")
    print("📥 INSERT main_table: id=2, name='Item_2', lookup_id=2 (Lookup 不存在)")
    
    time.sleep(1)
    
    # 查詢結果
    result = client.query("SELECT * FROM test.imv_target WHERE id = 2")
    print(f"\n📊 Target 表結果 (Lookup 不存在時):")
    for row in result.result_rows:
        print(f"   id={row[0]}, name={row[1]}, category={row[2] if row[2] else 'NULL'}")
    
    # 現在插入 Lookup 資料
    client.command("INSERT INTO test.lookup_table VALUES (2, 'Category_B')")
    print("\n📥 INSERT lookup_table: id=2, category='Category_B'")
    
    time.sleep(1)
    
    # 再次查詢
    result = client.query("SELECT * FROM test.imv_target WHERE id = 2")
    print(f"\n📊 Target 表結果 (Lookup 插入後):")
    for row in result.result_rows:
        print(f"   id={row[0]}, name={row[1]}, category={row[2] if row[2] else 'NULL'}")
    
    if result.result_rows and (result.result_rows[0][2] == '' or result.result_rows[0][2] is None):
        print("\n⚠️ 關鍵發現: Lookup 表後來插入的資料，不會更新已寫入 Target 的記錄!")
    else:
        print("\n✅ category 有值")


def test_scenario_3():
    """測試 3: 更新 Lookup 表的資料"""
    print("\n" + "=" * 60)
    print("Test 3: 更新 Lookup 表的資料")
    print("=" * 60)
    
    # 查詢 id=1 的當前狀態
    result = client.query("SELECT * FROM test.imv_target WHERE id = 1")
    print(f"📊 更新前 Target 表 (id=1):")
    for row in result.result_rows:
        print(f"   id={row[0]}, name={row[1]}, category={row[2]}")
    
    # 更新 Lookup 表 (ClickHouse 用 ALTER + DELETE + INSERT 模擬)
    client.command("ALTER TABLE test.lookup_table DELETE WHERE id = 1")
    client.command("INSERT INTO test.lookup_table VALUES (1, 'Category_A_Updated')")
    print("\n📝 UPDATE lookup_table: id=1, category='Category_A' → 'Category_A_Updated'")
    
    time.sleep(2)  # 等待 mutation 完成
    
    # 查詢 Lookup 表確認更新
    lookup_result = client.query("SELECT * FROM test.lookup_table WHERE id = 1")
    print(f"\n📊 Lookup 表確認:")
    for row in lookup_result.result_rows:
        print(f"   id={row[0]}, category={row[1]}")
    
    # 查詢 Target 表
    result = client.query("SELECT * FROM test.imv_target WHERE id = 1")
    print(f"\n📊 更新後 Target 表 (id=1):")
    for row in result.result_rows:
        print(f"   id={row[0]}, name={row[1]}, category={row[2]}")
    
    if result.result_rows and result.result_rows[0][2] == 'Category_A':
        print("\n⚠️ 關鍵發現: Lookup 表更新後，Target 表的舊記錄不會自動更新!")


def test_scenario_4():
    """測試 4: 新的主表 INSERT 會使用最新的 Lookup 資料"""
    print("\n" + "=" * 60)
    print("Test 4: 新的主表 INSERT 會使用最新的 Lookup 資料")
    print("=" * 60)
    
    # 插入新的主表記錄，使用已更新的 lookup_id=1
    client.command("INSERT INTO test.main_table (id, name, lookup_id) VALUES (3, 'Item_3', 1)")
    print("📥 INSERT main_table: id=3, name='Item_3', lookup_id=1")
    
    time.sleep(1)
    
    # 查詢結果
    result = client.query("SELECT * FROM test.imv_target WHERE id = 3")
    print(f"\n📊 Target 表結果 (新記錄):")
    for row in result.result_rows:
        print(f"   id={row[0]}, name={row[1]}, category={row[2]}")
    
    if result.result_rows and result.result_rows[0][2] == 'Category_A_Updated':
        print("\n✅ 新記錄使用了最新的 Lookup 資料!")


def show_summary():
    """顯示測試總結"""
    print("\n" + "=" * 60)
    print("測試總結")
    print("=" * 60)
    
    # 顯示所有 Target 資料
    result = client.query("SELECT * FROM test.imv_target ORDER BY id")
    print("\n📊 Target 表完整資料:")
    print("-" * 50)
    print(f"{'id':<5} {'name':<10} {'category':<20}")
    print("-" * 50)
    for row in result.result_rows:
        print(f"{row[0]:<5} {row[1]:<10} {row[2] if row[2] else 'NULL':<20}")
    
    print("\n" + "=" * 60)
    print("結論")
    print("=" * 60)
    print("""
1. ✅ 主表 INSERT 時，MView 會觸發，並 JOIN 當下的 Lookup 資料
2. ❌ Lookup 表 INSERT/UPDATE 時，MView 不會觸發
3. ❌ 已寫入 Target 的記錄，不會因為 Lookup 表變更而更新
4. ✅ 新的主表 INSERT 會使用最新的 Lookup 資料

對你專案的影響：
- 如果維度表（如 DMP_USER_INFO）的資料會變更
- 使用增量 MView 會導致歷史記錄的維度資訊過時
- 全量刷新（REFRESH EVERY）可以確保資料一致性
    """)


def cleanup():
    """清理測試資料"""
    print("\n清理測試資料...")
    client.command("DROP VIEW IF EXISTS test.imv_join_test")
    client.command("DROP TABLE IF EXISTS test.imv_target")
    client.command("DROP TABLE IF EXISTS test.main_table")
    client.command("DROP TABLE IF EXISTS test.lookup_table")
    print("✅ 清理完成")


if __name__ == "__main__":
    try:
        setup_test_tables()
        test_scenario_1()
        test_scenario_2()
        test_scenario_3()
        test_scenario_4()
        show_summary()
        cleanup()  # 自動清理
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
