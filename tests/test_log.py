
from socialdrop.log import bind_drop, log_event, unbind_drop


def test_log_event(capsys):
    bind_drop("drop-123")
    log_event("publish.started", platform="youtube")
    unbind_drop()
    captured = capsys.readouterr()
    assert "drop-123" in captured.out
    assert "publish.started" in captured.out
