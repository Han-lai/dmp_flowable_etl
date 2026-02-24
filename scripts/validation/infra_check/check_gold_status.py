import requests
import sys

# User specified port 8121
url = "http://10.136.218.207:8121"
auth = ('default', 'default')  # Update to use 'default' password found in other scripts

def run_query(query):
    print(f"Executing: {query}")
    try:
        # Using post for queries is standard for CH HTTP interface
        response = requests.post(url, params={'query': query}, auth=auth)
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return None
        return response.text.strip()
    except Exception as e:
        print(f"Exception: {e}")
        return None

def check_gold_status():
    # 1. List tables in gold
    print("--- Listing tables in gold database ---")
    tables_resp = run_query("SHOW TABLES FROM gold")
    if not tables_resp:
        print("Could not list tables.")
        return

    tables = tables_resp.split('\n')
    print(f"Found tables: {tables}")

    # 2. Check each table
    for table in tables:
        if not table: continue
        full_table = f"gold.{table}"
        print(f"\nChecking table: {full_table}")
        
        # Check count
        count_resp = run_query(f"SELECT count() FROM {full_table}")
        if count_resp:
            print(f"Row count: {count_resp}")
        else:
            print("Count failed.")

        # Check max date if possible (assuming snapshot_date exists based on previous files)
        try:
            # We don't know for sure if snapshot_date exists in all, but we saw it in sql files
            max_date_resp = run_query(f"SELECT max(snapshot_date) FROM {full_table}")
            if max_date_resp:
                print(f"Max snapshot_date: {max_date_resp}")
        except:
            print("Could not get max snapshot_date")

if __name__ == "__main__":
    check_gold_status()
