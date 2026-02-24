
import clickhouse_connect

def main():
    safe_config = {
        "host": "REDACTED_IP",
        "port": 8121,
        "username": "dmp_safe",
        "password": "dmp_safe",
        "database": "default"
    }

    print("Checking if 'dmp_safe' can login...")
    try:
        client = clickhouse_connect.get_client(**safe_config)
        print("✅ LOGIN SUCCESS: 'dmp_safe' still exists!")
        print("This means it was NOT removed from users.xml (or server didn't restart).")
    except Exception as e:
        print(f"❌ LOGIN FAILED: {e}")
        print("This suggests 'dmp_safe' might representatively be removed, or password wrong.")

if __name__ == "__main__":
    main()
