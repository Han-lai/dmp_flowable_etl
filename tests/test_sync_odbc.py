from scripts.etl.sync_unified_odbc import generate_batches

def test_generate_batches_basic():
    # Test simple 7 day batches over 14 days
    batches = generate_batches("2025-01-01", "2025-01-15", step_days=7)
    assert len(batches) == 3
    assert batches[0][0] == "2025-01-01 00:00:00"
    assert batches[0][1] == "2025-01-08 00:00:00"
    assert batches[1][0] == "2025-01-08 00:00:00"
    assert batches[1][1] == "2025-01-15 00:00:00"
    assert batches[2][0] == "2025-01-15 00:00:00"
    assert "2025-01-15 23:59:59" in batches[2][1]

def test_generate_batches_remainder():
    # Test 7 day batches over 10 days
    batches = generate_batches("2025-01-01", "2025-01-10", step_days=7)
    assert len(batches) == 2
    assert batches[0][0] == "2025-01-01 00:00:00"
    assert batches[0][1] == "2025-01-08 00:00:00"
    assert batches[1][0] == "2025-01-08 00:00:00"
    # Remainder clamped to end date
    assert "2025-01-10 23:59:59" in batches[1][1]

def test_generate_batches_hours():
    # Test hour-based batches
    batches = generate_batches("2025-01-01 00:00:00", "2025-01-01 12:00:00", step_days=0, step_hours=4)
    assert len(batches) == 3
    assert batches[0][1] == "2025-01-01 04:00:00"
    assert batches[1][1] == "2025-01-01 08:00:00"
    assert batches[-1][1] == "2025-01-01 12:00:00"
