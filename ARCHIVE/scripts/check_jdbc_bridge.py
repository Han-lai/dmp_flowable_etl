"""檢查 JDBC Bridge 狀態"""
import requests

def main():
    print("檢查 JDBC Bridge 狀態...")
    
    # 直接測試 JDBC Bridge 服務
    try:
        resp = requests.get("http://localhost:9019/", timeout=5)
        print(f"✅ JDBC Bridge 服務回應: {resp.status_code}")
    except Exception as e:
        print(f"❌ JDBC Bridge 服務無法連線: {e}")
        print("\n請確認:")
        print("1. jdbc-bridge 容器有啟動")
        print("2. port 9019 有正確映射")
        print("\n執行: docker ps | findstr jdbc")
        return
    
    # 測試 datasources
    try:
        resp = requests.get("http://localhost:9019/datasources", timeout=5)
        print(f"\n已設定的 Datasources:")
        print(resp.text)
    except Exception as e:
        print(f"無法取得 datasources: {e}")

if __name__ == "__main__":
    main()
