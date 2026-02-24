
import clickhouse_connect
import time

def main():
    # Admin connection
    admin_config = {
        "host": "REDACTED_IP",
        "port": 8121,
        "username": "default",
        "password": "default",
        "database": "default"
    }




    print("--- 1. Checking if 'dmp_safe' already exists and works ---")
    safe_config = {
        "host": "REDACTED_IP",
        "port": 8121,
        "username": "dmp_safe",
        "password": "dmp_safe",
        "database": "bronze"
    }


    
    print("\n--- 2. CORRECTING PERMISSIONS ---")
    try:
        client = clickhouse_connect.get_client(**admin_config)
        
        print("Revoking destructive permissions on 'bronze' schema...")
        # We need to make sure we are not failing if revocation fails because of no grant?
        # No, REVOKE should work if we have permissions.
        try:
            client.command("REVOKE DROP, TRUNCATE ON bronze.* FROM dmp_safe")
            print("✅ Revoke command executed.")
        except Exception as e:
             print(f"❌ Revoke failed: {e}")
             if "ACCESS_DENIED" in str(e):
                 print("CRITICAL: 'default' user still lacks privileges to REVOKE.")
                 print("Please ensure <access_management>1</access_management> is in users.xml.")

        # Let's also ensure they HAVE basic permissions
        # client.command("GRANT ALL ON *.* TO dmp_safe WITH GRANT OPTION")

    except Exception as e:
        print(f"Could not connect as default to fix permissions: {e}")

    # 3. Verification
    print("\n--- 3. Re-Verifying Permissions ---")
    
    # Reconnect as safe user
    try:
        safe_client = clickhouse_connect.get_client(**safe_config)

        try:
            # Test 1: SELECT
            print("Testing SELECT (expect Success)...")
            safe_client.command("SELECT 1")
            print("✅ SELECT works.")
            
            # Test 2: INSERT (expect Success - strictly speaking we didn't block INSERT, let's verify if we should)
            # We only wanted to block DROP/TRUNCATE.
            
            # Test 3: DROP (Expect FAILURE)
            print("Testing DROP (expect FAILURE)...")
            try:
                # We can't actually drop a real table. 
                # And we can't create a table to drop if we don't have CREATE permissions? 
                # Wait, dmp_safe HAS CREATE permissions globally.
                # It only lacks DROP on BRONZE.
                
                # Try to create a dummy table in bronze
                try:
                    safe_client.command("CREATE TABLE IF NOT EXISTS bronze._test_verify_security (id Int8) ENGINE = Log")
                    print("  Created dummy table in bronze (Allowed).")
                except Exception as e:
                    print(f"  Could not create dummy table: {e}")

                # Try to DROP it
                safe_client.command("DROP TABLE bronze._test_verify_security")
                print("❌ WARNING: DROP SUCCEEDED! The user IS NOT unrestricted.")
            except Exception as e:
                if "Not enough privileges" in str(e) or "ACCESS_DENIED" in str(e):
                    print(f"✅ SUCCESS: DROP was blocked! Error message: {e}")
                else:
                    print(f"⚠️ Unexpected error during DROP test: {e}")
                    
        except Exception as e:
            print(f"Verification process blocked: {e}")


if __name__ == "__main__":
    main()
