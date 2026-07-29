import pytest
from unittest.mock import MagicMock
import sys
import os

# Ensure the project root is in sys.path so tests can import 'api' and 'scripts'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# scripts/etl 也要加：該目錄的模組彼此以平面名稱互相 import（sync_unified_odbc → setup_schema），
# 只加專案根目錄會讓整份 test_sync_odbc.py 在 collection 階段就 ImportError。
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'etl')))

@pytest.fixture
def mock_clickhouse_client():
    client = MagicMock()
    # Default behavior for system.parts or row count queries
    def query_side_effect(sql):
        res = MagicMock()
        if "ops_metrics.etl_checkpoint" in sql:
            res.result_rows = [] # default no checkpoint
        elif "system.parts" in sql:
            res.result_rows = [[100, 1024]]
        elif "count()" in sql:
            res.result_rows = [[10]] # default window is not empty
        else:
            res.result_rows = []
        return res
    client.query.side_effect = query_side_effect
    return client
