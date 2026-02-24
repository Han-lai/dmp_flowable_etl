import clickhouse_connect

HOST = 'REDACTED_IP'
PORTS = [8121, 8123]
PASSWORDS = ['default', '', 'clickhouse']

def test_conn():
    for port in PORTS:
        for pwd in PASSWORDS:
            print(f"Testing {HOST}:{port} with user='default', pass='{pwd}'")
            try:
                client = clickhouse_connect.get_client(host=HOST, port=port, username='default', password=pwd, connect_timeout=5)
                client.query("SELECT 1")
                print(f"SUCCESS! Port: {port}, Password: '{pwd}'")
                return
            except Exception as e:
                print(f"Failed: {e}")

if __name__ == "__main__":
    test_conn()
