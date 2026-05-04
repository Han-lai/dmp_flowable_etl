import pytest
from unittest.mock import MagicMock

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
