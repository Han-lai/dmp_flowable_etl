


import clickhouse_connect
import time

def main():
    admin_config = {
        "host": "10.136.218.207",
        "port": 8121,
        "username": "default",
        "password": "default",
        "database": "default"
    }

    safe_config = {
        "host": "10.136.218.207",
        "port": 8121,
        "username": "dmp_safe",
        "password": "dmp_safe",
        "database": "default"
    }


    print("=== STEP 1: Admin Configuration (Using 'default') ===")
    try:
        client = clickhouse_connect.get_client(**admin_config)
        
        # Try self-promotion if possible (since grantees_any=1)
        print("1.0 Attempting to self-grant 'CREATE USER'...")
        try:
            client.command("GRANT CREATE USER ON *.* TO default")
            print("   ✅ Self-grant succeeded (or was ignored).")
        except Exception as e:
            print(f"   ⚠️ Self-grant failed: {e}")

        # Ensure user exists and has permissions
        print("1.1 Ensuring 'dmp_safe' exists and has permissions...")
        client.command("CREATE USER IF NOT EXISTS dmp_safe IDENTIFIED WITH sha256_password BY 'dmp_safe'")
        client.command("GRANT ALL ON *.* TO dmp_safe WITH GRANT OPTION")
        
        # The Critical Step: Revoke DROP/TRUNCATE on bronze
        print("1.2 Revoking DROP/TRUNCATE on 'bronze' database...")
        client.command("REVOKE DROP, TRUNCATE ON bronze.* FROM dmp_safe")
        print("✅ Account configured successfully.")

    except Exception as e:
        print(f"❌ Admin configuration failed: {e}")
        print("Please ensure 'default' user has <access_management>1</access_management> in users.xml")
        return

    print("\n=== STEP 2: Verifying 'bronze' Protection (Using 'dmp_safe') ===")
    try:
        safe_client = clickhouse_connect.get_client(**safe_config)
        
        # 2.1 Try to Create a test table in Bronze (Should be Allowed)
        # We need a table to try and drop
        print("2.1 Creating dummy table 'bronze._test_protection'...")
        safe_client.command("CREATE TABLE IF NOT EXISTS bronze._test_protection (id Int8) ENGINE = Memory")
        print("   ✅ Creation Allowed (Correct)")
        
        # 2.2 Try to Insert (Should be Allowed)
        print("2.2 Inserting data...")
        safe_client.command("INSERT INTO bronze._test_protection VALUES (1)")
        print("   ✅ Insert Allowed (Correct)")
        
        # 2.3 Try to TRUNCATE (Should FAIL)
        print("2.3 Attempting TRUNCATE (Expect FAILURE)...")
        try:
            safe_client.command("TRUNCATE TABLE bronze._test_protection")
            print("   ❌ FAIL: TRUNCATE SUCCEEDED! Protection is NOT working.")
        except Exception as e:
            if "NOT_ENOUGH_PRIVILEGES" in str(e) or "ACCESS_DENIED" in str(e):
                print(f"   ✅ SUCCESS: TRUNCATE blocked. ({e})")
            else:
                print(f"   ⚠️ Unexpected error: {e}")

        # 2.4 Try to DROP (Should FAIL)
        print("2.4 Attempting DROP (Expect FAILURE)...")
        try:
            safe_client.command("DROP TABLE bronze._test_protection")
            print("   ❌ FAIL: DROP SUCCEEDED! Protection is NOT working.")
        except Exception as e:
             if "NOT_ENOUGH_PRIVILEGES" in str(e) or "ACCESS_DENIED" in str(e):
                print(f"   ✅ SUCCESS: DROP blocked. ({e})")
             else:
                print(f"   ⚠️ Unexpected error: {e}")

    except Exception as e:
        print(f"❌ Verification Step 2 failed: {e}")

    print("\n=== STEP 3: Verifying 'silver' Access (Using 'dmp_safe') ===")
    try:
        # 3.1 Try to Create a test table in Silver (Should be Allowed)
        print("3.1 Creating dummy table 'silver._test_access'...")
        # Ensure silver db exists (Admin does this just in case)
        client.command("CREATE DATABASE IF NOT EXISTS silver")
        
        safe_client.command("CREATE TABLE IF NOT EXISTS silver._test_access (id Int8) ENGINE = Memory")
        print("   ✅ Creation Allowed (Correct)")
        
        # 3.2 Try to Insert (Should be Allowed)
        print("3.2 Inserting data...")
        safe_client.command("INSERT INTO silver._test_access VALUES (1)")
        print("   ✅ Insert Allowed (Correct)")
        
        # 3.3 Try to DROP (Should be Allowed in Silver)
        print("3.3 Attempting DROP (Expect SUCCESS)...")
        safe_client.command("DROP TABLE silver._test_access")
        print("   ✅ DROP Succeeded (Correct)")

    except Exception as e:
        print(f"❌ Verification Step 3 failed: {e}")

    print("\n=== Cleanup (Using Admin) ===")
    try:
        client.command("DROP TABLE IF EXISTS bronze._test_protection")
        print("Cleaned up bronze._test_protection")
    except Exception as e:
        print(f"Cleanup failed: {e}")

if __name__ == "__main__":
    main()

