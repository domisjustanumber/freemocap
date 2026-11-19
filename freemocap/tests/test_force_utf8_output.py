import io
import sys


def test_force_utf8_output_reconfigures_cp1252_and_tolerates_missing_streams(monkeypatch):
    from freemocap.__main__ import force_utf8_output

    piped = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", piped)
    monkeypatch.setattr(sys, "stderr", None)
    force_utf8_output()
    assert piped.encoding == "utf-8"
    piped.write("└>> line")
    piped.flush()
    assert piped.buffer.getvalue() == "└>> line".encode("utf-8")

    monkeypatch.setattr(sys, "stdout", object())
    force_utf8_output()
