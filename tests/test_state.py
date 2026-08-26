from pathlib import Path

from socialdrop import state as state_mod


def make_drop(tmp_path: Path, schedule: str | None = None) -> Path:
    (tmp_path / "v.mp4").write_bytes(b"x" * 32)
    sched = f'schedule: "{schedule}"' if schedule else 'schedule: ""'
    md = tmp_path / "v.md"
    md.write_text(f"---\ntitle: V\n{sched}\nplatforms:\n  mock: {{}}\n---\n")
    return md


def test_new_state_and_roundtrip(tmp_path: Path):
    md = make_drop(tmp_path)
    st = state_mod.new_state(md, ["mock"])
    state_mod.save_state(md, st)
    loaded = state_mod.load_state(md)
    assert loaded is not None
    assert loaded.platforms["mock"].status == "discovered"


def test_status_transitions_to_published(tmp_path: Path):
    md = make_drop(tmp_path)
    st = state_mod.new_state(md, ["mock"])
    attempt = st.attempt("mock")
    attempt.status = "published"
    state_mod.save_state(md, st)
    assert st.status == "published"
    assert state_mod.load_state(md).all_published


def test_is_due_without_schedule(tmp_path: Path):
    md = make_drop(tmp_path)
    assert state_mod.is_due(md)


def test_is_due_future_schedule_not_due(tmp_path: Path):
    md = make_drop(tmp_path, schedule="2099-01-01 10:00 UTC")
    assert not state_mod.is_due(md)


def test_is_due_past_schedule_due(tmp_path: Path):
    md = make_drop(tmp_path, schedule="2001-01-01 10:00 UTC")
    assert state_mod.is_due(md)


def test_reset_platform_clears_error(tmp_path: Path):
    md = make_drop(tmp_path)
    st = state_mod.new_state(md, ["mock"])
    attempt = st.attempt("mock")
    attempt.status = "failed"
    attempt.error = "boom"
    state_mod.save_state(md, st)
    state_mod.reset_platform(md, "mock")
    reloaded = state_mod.load_state(md)
    assert reloaded.platforms["mock"].status == "discovered"
    assert reloaded.platforms["mock"].error is None


def test_now_utc():
    assert state_mod._now_iso().endswith("Z")
