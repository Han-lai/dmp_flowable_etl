from fastapi.testclient import TestClient
import pytest
from unittest.mock import MagicMock
from api.main import app, get_date_info

client = TestClient(app)

def test_api_invalid_date_format():
    # Test passing a bad month format
    response = client.get("/api/l5/task-report", params={"month": "202512"}) # Should be 2025-12
    assert response.status_code == 500
    assert "Invalid month format" in response.json()["detail"] or "500" in str(response.status_code)

def test_get_date_info_logic():
    # Test date calculation logic
    info = get_date_info("2026-01")
    assert info["year"] == 2026
    assert info["month_num"] == 1
    # January 2026 has 31 days
    # The last 7 days from Jan 31 are: 31, 30, 29, 28, 27, 26, 25
    assert len(info["days"]) == 7
    assert "2026-01-31" in info["days"]
    
    # Check weeks - should generate 3 weeks
    assert len(info["weeks"]) == 3
    # Check if W5 is there (since Jan 31 is around Week 5)
    assert any("W" in week for week in info["weeks"])

@pytest.fixture
def override_get_db():
    # Mock the database client to prevent real connection
    mock_client = MagicMock()
    
    # Mock a response for the L5 report query
    mock_res = MagicMock()
    # The query returns: p_type, label, total, todo, doing, done, acc
    mock_res.result_rows = [
        ("Monthly", "Total", 100, 10, 20, 70, 30),
        ("Daily", "2025-12-31", 50, 5, 10, 35, 15),
        ("Weekly", "W52", 100, 10, 20, 70, 30)
    ]
    mock_client.query.return_value = mock_res
    
    # Replace dependency in app
    from api.main import get_db
    app.dependency_overrides[get_db] = lambda: mock_client
    yield mock_client
    app.dependency_overrides.clear()

def test_api_valid_request(mocker, override_get_db):
    # Mock get_db explicitly in the module if dependency override is not used
    mocker.patch("api.main.get_db", return_value=override_get_db)
    
    response = client.get("/api/l5/task-report", params={"month": "2025-12", "vxtype": "V3"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    
    # Check if the rows are populated
    rows = data["data"]["rows"]
    assert len(rows) > 0
    # There should be rows for "Total Task", "Todo", "Doing", "Done", etc.
    assert any(row["status"] == "Todo" for row in rows)
