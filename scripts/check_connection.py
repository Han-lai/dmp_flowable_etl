import requests
import sys

host = "REDACTED_IP"
port = 8121
auth = ('default', 'default')

def try_url(scheme):
    url = f"{scheme}://{host}:{port}"
    print(f"Trying {url}...")
    try:
        response = requests.get(url, auth=auth, timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:100]}")
        return True
    except requests.exceptions.Timeout:
        print("Timeout.")
    except Exception as e:
        print(f"Error: {e}")
    return False

if __name__ == "__main__":
    if not try_url("http"):
        print("HTTP failed.")
        try_url("https")
