import scripts.etl.sync_unified_odbc as sync
from scripts.etl.sync_unified_odbc import generate_batches, mask_secrets, odbc_escape_value

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


def test_odbc_escape_wraps_and_doubles_closing_brace():
    # 含 ! 的密碼裸寫會被 bridge 拒收（BAD_ODBC_CONNECTION_STRING）；} 須依 ODBC 規則加倍
    assert odbc_escape_value("Ab1!c#d") == "{Ab1!c#d}"
    assert odbc_escape_value("ab}c") == "{ab}}c}"


def test_mask_secrets_hides_password_in_all_connection_string_forms():
    forms = [
        "Pwd={Ab1!c};MARS_Connection=no",                       # 明文 DDL
        "...Pwd%3D%7BAb1%21c%7D%3BMARS_Connection%3Dno&x=1",    # bridge URL（大括號）
        "...Pwd%3DAb1%21c%3BMARS_Connection%3Dno&x=1",          # bridge URL（舊裸寫）
    ]
    for text in forms:
        masked = mask_secrets(text)
        assert "[HIDDEN]" in masked
        assert "Ab1" not in masked and "Ab1%21" not in masked


def test_mask_secrets_does_not_leak_tail_of_password_containing_brace(monkeypatch):
    # 密碼含 } 時轉義成 {ab}}c}，非貪婪比對會停在第一個 } 而漏出尾段
    monkeypatch.setattr(sync, "MSSQL_PASSWORD", "")   # 只驗 regex 防線，繞過字面抽換
    masked = mask_secrets("Pwd={ab}}c};MARS_Connection=no")
    assert masked == "Pwd=[HIDDEN];MARS_Connection=no"


def test_mask_secrets_keeps_surrounding_message_intact():
    masked = mask_secrets("Code: 86. connection_string=DSN%3DX%3BPwd%3D%7Bp%7D%3BMARS_Connection%3Dno. HTTP 500")
    assert masked.startswith("Code: 86.")
    assert masked.endswith("%3BMARS_Connection%3Dno. HTTP 500")
