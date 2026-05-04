import datetime
from scripts.etl.execute_etl import generate_windows

def test_generate_windows_single_step():
    # Test one month chunked by 10 days
    windows = generate_windows("2025-01-01", "2025-01-31", 10)
    
    # Assert total length
    assert len(windows) == 4
    
    # Assert first window
    assert windows[0][0] == datetime.datetime(2025, 1, 1, 0, 0, 0)
    assert windows[0][1] == datetime.datetime(2025, 1, 10, 23, 59, 59)
    
    # Assert second window
    assert windows[1][0] == datetime.datetime(2025, 1, 11, 0, 0, 0)
    assert windows[1][1] == datetime.datetime(2025, 1, 20, 23, 59, 59)
    
    # Assert last window (1 day remainder)
    assert windows[-1][0] == datetime.datetime(2025, 1, 31, 0, 0, 0)
    assert windows[-1][1] == datetime.datetime(2025, 1, 31, 23, 59, 59)

def test_generate_windows_boundary_exact():
    # Test chunking that perfectly divides
    windows = generate_windows("2025-01-01", "2025-01-20", 10)
    assert len(windows) == 2
    assert windows[1][0] == datetime.datetime(2025, 1, 11, 0, 0, 0)
    assert windows[1][1] == datetime.datetime(2025, 1, 20, 23, 59, 59)
