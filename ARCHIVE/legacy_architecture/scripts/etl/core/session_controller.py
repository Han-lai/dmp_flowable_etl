#!/usr/bin/env python3
"""
ClickHouse Session 控制器
解決 SESSION_IS_LOCKED 錯誤，提供會話隔離和重試機制
"""

import time
import uuid
import logging
from contextlib import contextmanager
from typing import Dict, Optional
import clickhouse_connect

logger = logging.getLogger(__name__)

class SessionRetryHandler:
    """Session 重試處理器"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    def should_retry(self, error: Exception) -> bool:
        """判斷是否應該重試"""
        error_str = str(error).lower()
        return "session_is_locked" in error_str or "session" in error_str and "locked" in error_str
    
    def get_delay(self, attempt: int) -> float:
        """計算重試延遲時間（指數退避）"""
        return self.base_delay * (2 ** attempt)

class SessionController:
    """ClickHouse Session 控制器"""
    
    def __init__(self, clickhouse_config: dict, retry_handler: Optional[SessionRetryHandler] = None):
        self.config = clickhouse_config
        self.retry_handler = retry_handler or SessionRetryHandler()
        self.active_sessions: Dict[str, any] = {}
        
    def generate_session_id(self, prefix: str = "batch") -> str:
        """生成唯一的 session ID"""
        timestamp = int(time.time() * 1000)
        unique_id = str(uuid.uuid4())[:8]
        return f"{prefix}_{timestamp}_{unique_id}"
    
    @contextmanager
    def get_session(self, session_prefix: str = "batch"):
        """取得會話連線（帶重試機制）"""
        session_id = self.generate_session_id(session_prefix)
        client = None
        
        try:
            for attempt in range(self.retry_handler.max_retries + 1):
                try:
                    # 建立新的會話連線
                    config_with_session = self.config.copy()
                    config_with_session['session_id'] = session_id
                    
                    client = clickhouse_connect.get_client(**config_with_session)
                    
                    # 測試連線
                    client.command("SELECT 1")
                    
                    self.active_sessions[session_id] = client
                    logger.info(f"✅ Session 建立成功: {session_id}")
                    
                    yield client
                    return
                    
                except Exception as e:
                    if self.retry_handler.should_retry(e) and attempt < self.retry_handler.max_retries:
                        delay = self.retry_handler.get_delay(attempt)
                        logger.warning(f"⚠️ Session 錯誤 (嘗試 {attempt + 1}/{self.retry_handler.max_retries + 1}): {e}")
                        logger.info(f"等待 {delay:.1f} 秒後重試...")
                        time.sleep(delay)
                        
                        # 生成新的 session ID 重試
                        session_id = self.generate_session_id(session_prefix)
                        continue
                    else:
                        logger.error(f"❌ Session 建立失敗: {e}")
                        raise
        
        finally:
            # 清理會話
            if session_id in self.active_sessions:
                try:
                    if client:
                        client.close()
                    del self.active_sessions[session_id]
                    logger.info(f"🧹 Session 已清理: {session_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Session 清理警告: {e}")
    
    @contextmanager
    def get_stateless_session(self):
        """取得無狀態會話（避免 session 衝突）"""
        try:
            client = clickhouse_connect.get_client(**self.config)
            client.command("SELECT 1")
            logger.info("✅ 無狀態 Session 建立成功")
            yield client
        except Exception as e:
            logger.error(f"❌ 無狀態 Session 建立失敗: {e}")
            raise
        finally:
            try:
                if 'client' in locals():
                    client.close()
                logger.info("🧹 無狀態 Session 已清理")
            except Exception as e:
                logger.warning(f"⚠️ 無狀態 Session 清理警告: {e}")
    
    def close_all_sessions(self):
        """關閉所有活動會話"""
        for session_id, client in list(self.active_sessions.items()):
            try:
                client.close()
                logger.info(f"🧹 Session 已關閉: {session_id}")
            except Exception as e:
                logger.warning(f"⚠️ 關閉 Session 警告 {session_id}: {e}")
        
        self.active_sessions.clear()
        logger.info("✅ 所有 Session 已清理")

# 測試函數
def test_session_controller():
    """測試 Session Controller"""
    config = {
        "host": "REDACTED_IP",
        "port": 8121,
        "username": "default",
        "password": "default",
        "database": "default"
    }
    
    controller = SessionController(config)
    
    try:
        # 測試普通會話
        with controller.get_session("test") as client:
            result = client.command("SELECT 'Hello from session'")
            print(f"會話測試結果: {result}")
        
        # 測試無狀態會話
        with controller.get_stateless_session() as client:
            result = client.command("SELECT 'Hello from stateless'")
            print(f"無狀態測試結果: {result}")
        
        print("✅ Session Controller 測試通過")
        
    except Exception as e:
        print(f"❌ Session Controller 測試失敗: {e}")
    
    finally:
        controller.close_all_sessions()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_session_controller()