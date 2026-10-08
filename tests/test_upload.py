from ui.upload import persist_csv_bytes, safe_filename


def test_safe_filename_removes_path_and_unsafe_chars():
    assert safe_filename("../../Mi equipo 2026.csv") == "Mi_equipo_2026.csv"


def test_persist_upload_is_content_addressed(tmp_path):
    raw = b"team,event_type\\nA,Pass\\n"
    p1, d1 = persist_csv_bytes(raw, "events.csv", tmp_path, "Arturo")
    p2, d2 = persist_csv_bytes(raw, "events.csv", tmp_path, "Arturo")
    assert p1 == p2
    assert d1 == d2
    assert p1.read_bytes() == raw
