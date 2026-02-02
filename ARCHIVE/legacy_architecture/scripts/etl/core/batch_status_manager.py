#!/usr/bin/env python3
"""
批次狀態管理器
負責批次控制表的狀態查詢、更新和管理
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class BatchStatus(Enum):
    """批次狀態枚舉 - 根據現有表結構調整"""
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'

@dataclass
class BatchInfo:
    """批次資訊資料類別"""
    table_name: str
    batch_id: str
    status: BatchStatus
    watermark_start: str
    watermark_end: str
    row_count: int = 0
    duration_seconds: float = 0.0
    error_message: str = ''
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class BatchStatusManager:
    """批次狀態管理器"""
    
    def __init__(self, clickhouse_client):
        self.client = clickhouse_client
        self._ensure_tables_exist()
    
    def _ensure_tables_exist(self):
        """確保控制表存在"""
        try:
            # 檢查表是否存在
            exists = self.client.command("EXISTS TABLE bronze.sync_batch_control")
            
            if not exists:
                logger.warning("bronze.sync_batch_control 表不存在")
                logger.info("請先建立批次控制表")
            else:
                logger.info("✅ 批次控制表已存在")
                
        except Exception as e:
            logger.error(f"檢查控制表失敗: {e}")
    
    def get_batch_info(self, table_name: str, batch_id: str) -> Optional[BatchInfo]:
        """取得批次資訊"""
        try:
            sql = """
            SELECT table_name, batch_id, status, watermark_start, watermark_end,
                   row_count, duration_seconds, error_message, created_at, updated_at
            FROM bronze.sync_batch_control FINAL
            WHERE table_name = %(table_name)s AND batch_id = %(batch_id)s
            """
            
            result = self.client.query(sql, parameters={
                'table_name': table_name,
                'batch_id': batch_id
            })
            
            if result.result_rows:
                row = result.result_rows[0]
                return BatchInfo(
                    table_name=row[0],
                    batch_id=row[1],
                    status=BatchStatus(row[2]),
                    watermark_start=row[3],
                    watermark_end=row[4],
                    row_count=row[5],
                    duration_seconds=row[6],
                    error_message=row[7],
                    created_at=row[8],
                    updated_at=row[9]
                )
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 取得批次資訊失敗: {e}")
            return None
    
    def update_batch_status(self, table_name: str, batch_id: str, 
                           status: BatchStatus, row_count: int = 0,
                           duration_seconds: float = 0.0, 
                           error_message: str = '') -> bool:
        """更新批次狀態"""
        try:
            sql = """
            INSERT INTO bronze.sync_batch_control 
            (table_name, batch_id, batch_start_time, batch_end_time,
             watermark_start, watermark_end, status, row_count, 
             duration_seconds, error_message, updated_at)
            SELECT 
                table_name, batch_id, batch_start_time, now64(3),
                watermark_start, watermark_end, %(status)s, %(row_count)s,
                %(duration_seconds)s, %(error_message)s, now64(3)
            FROM bronze.sync_batch_control FINAL
            WHERE table_name = %(table_name)s AND batch_id = %(batch_id)s
            """
            
            params = {
                'table_name': table_name,
                'batch_id': batch_id,
                'status': status.value,
                'row_count': row_count,
                'duration_seconds': duration_seconds,
                'error_message': error_message
            }
            
            self.client.command(sql, parameters=params)
            logger.info(f"✅ 批次狀態已更新: {batch_id} -> {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 更新批次狀態失敗: {e}")
            return False
    
    def get_failed_batches(self, table_name: str = None) -> List[BatchInfo]:
        """取得失敗的批次列表"""
        try:
            if table_name:
                sql = """
                SELECT table_name, batch_id, status, watermark_start, watermark_end,
                       row_count, duration_seconds, error_message, created_at, updated_at
                FROM bronze.sync_batch_control FINAL
                WHERE table_name = %(table_name)s AND status = 'failed'
                ORDER BY watermark_start
                """
                params = {'table_name': table_name}
            else:
                sql = """
                SELECT table_name, batch_id, status, watermark_start, watermark_end,
                       row_count, duration_seconds, error_message, created_at, updated_at
                FROM bronze.sync_batch_control FINAL
                WHERE status = 'failed'
                ORDER BY table_name, watermark_start
                """
                params = {}
            
            result = self.client.query(sql, parameters=params)
            
            batches = []
            for row in result.result_rows:
                batches.append(BatchInfo(
                    table_name=row[0],
                    batch_id=row[1],
                    status=BatchStatus(row[2]),
                    watermark_start=row[3],
                    watermark_end=row[4],
                    row_count=row[5],
                    duration_seconds=row[6],
                    error_message=row[7],
                    created_at=row[8],
                    updated_at=row[9]
                ))
            
            return batches
            
        except Exception as e:
            logger.error(f"❌ 取得失敗批次失敗: {e}")
            return []
    
    def get_sync_progress(self, table_name: str = None) -> List[Dict[str, Any]]:
        """取得同步進度"""
        try:
            if table_name:
                sql = """
                SELECT 
                    table_name,
                    COUNT(*) as total_batches,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_batches,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_batches,
                    SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_batches,
                    MAX(watermark_end) as latest_watermark,
                    SUM(row_count) as total_rows
                FROM bronze.sync_batch_control FINAL
                WHERE table_name = %(table_name)s
                GROUP BY table_name
                """
                params = {'table_name': table_name}
            else:
                sql = """
                SELECT 
                    table_name,
                    COUNT(*) as total_batches,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_batches,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_batches,
                    SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_batches,
                    MAX(watermark_end) as latest_watermark,
                    SUM(row_count) as total_rows
                FROM bronze.sync_batch_control FINAL
                GROUP BY table_name
                ORDER BY table_name
                """
                params = {}
            
            result = self.client.query(sql, parameters=params)
            
            progress_list = []
            for row in result.result_rows:
                progress_list.append({
                    'table_name': row[0],
                    'total_batches': row[1],
                    'completed_batches': row[2],
                    'failed_batches': row[3],
                    'running_batches': row[4],
                    'latest_watermark': row[5],
                    'total_rows': row[6],
                    'success_rate': (row[2] / row[1] * 100) if row[1] > 0 else 0
                })
            
            return progress_list
            
        except Exception as e:
            logger.error(f"❌ 取得同步進度失敗: {e}")
            return []

# 測試函數
def test_batch_status_manager():
    """測試批次狀態管理器"""
    import clickhouse_connect
    
    config = {
        "host": "10.136.218.207",
        "port": 8121,
        "username": "default",
        "password": "default",
        "database": "default"
    }
    
    client = clickhouse_connect.get_client(**config)
    manager = BatchStatusManager(client)
    
    # 測試取得失敗批次
    failed_batches = manager.get_failed_batches()
    print(f"失敗批次數量: {len(failed_batches)}")
    
    for batch in failed_batches:
        print(f"- {batch.batch_id}: {batch.status.value} ({batch.error_message[:50]}...)")
    
    # 測試取得同步進度
    progress = manager.get_sync_progress()
    print(f"\n同步進度:")
    for p in progress:
        print(f"- {p['table_name']}: {p['completed_batches']}/{p['total_batches']} 完成 ({p['success_rate']:.1f}%)")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_batch_status_manager()