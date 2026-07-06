from scripts.etl.audit_done_details import audit_done_details
from unittest.mock import MagicMock
import pytest

def test_audit_done_details_query_builder(mocker):
    # Mock ClickHouse client
    mock_client = MagicMock()
    mock_res = MagicMock()
    mock_res.result_rows = []
    mock_client.query.return_value = mock_res

    mocker.patch("scripts.etl.audit_done_details.get_client", return_value=mock_client)

    # 1. Test TODO status logic
    audit_done_details("2025-12-25", "CNE", "WJ2", "NBU", "E5", "V3", "todo")

    mock_client.query.assert_called_once()
    called_sql = mock_client.query.call_args[0][0]
    called_params = mock_client.query.call_args.kwargs["parameters"]

    # Query must use parameterized placeholders, not string-interpolated literals (SQL injection fix).
    assert "region = {p_region:String}" in called_sql
    assert "task_start_date = {p_date:Date}" in called_sql
    assert called_params["p_region"] == "CNE"
    assert called_params["p_date"] == "2025-12-25"
    # Check if the specific Todo compensation logic is there
    assert "COALESCE(task_claim_date, toDate('1900-01-01')) !=" in called_sql

    mock_client.query.reset_mock()

    # 2. Test DONE status logic
    audit_done_details("2025-12-31", None, None, None, None, None, "done")
    called_sql_done = mock_client.query.call_args[0][0]
    called_params_done = mock_client.query.call_args.kwargs["parameters"]

    assert "task_start_date = {p_date:Date}" in called_sql_done
    assert "task_end_date = {p_date:Date}" in called_sql_done
    assert called_params_done["p_date"] == "2025-12-31"
    # No hierarchy filters passed -> region/plant/etc placeholders must be absent
    assert "region" not in called_params_done
