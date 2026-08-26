import json
from pathlib import Path

from socialdrop.publisher import publish_drop
from socialdrop.schema import find_drops, load_drop


def make_json_drop(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "EI-002-Two-Kinds-Of-Memory.mp4").write_bytes(b"x" * 32)
    sidecar = tmp_path / "EI-002.json"
    sidecar.write_text(
        json.dumps(
            {
                "episode": "EI-002",
                "file": "EI-002-Two-Kinds-Of-Memory.mp4",
                "youtube": {
                    "title": 'RAM vs Storage: Why Your Phone Calls Both of Them "Space"',
                    "description": "Storage is the filing cabinet. RAM is the desk.",
                    "tags": "ram vs storage, what is ram, phone memory explained",
                    "category": "Science & Technology",
                    "madeForKids": False,
                    "license": "standard",
                },
                "instagram": {"caption": "Your phone has two kinds of memory.\n#ram #storage"},
                "tiktok": {"caption": "One stops you. The other slows you down."},
            }
        )
    )
    return sidecar


def test_finds_and_loads_json_sidecar(tmp_path: Path):
    md = make_json_drop(tmp_path)
    assert find_drops(tmp_path) == [md]
    drop = load_drop(md)
    assert drop.video_path.name == "EI-002-Two-Kinds-Of-Memory.mp4"
    assert drop.meta.platform_names == ["youtube", "instagram", "tiktok"]
    yt = drop.meta.platforms["youtube"]
    assert yt.get("title").startswith("RAM vs Storage")
    assert yt.get("category") == "Science & Technology"


def test_youtube_tags_comma_string_parsed(tmp_path: Path):
    from socialdrop.platforms.adapters import YOUTUBE_CATEGORY_IDS

    make_json_drop(tmp_path)
    drop = load_drop(find_drops(tmp_path)[0])
    raw = drop.meta.platforms["youtube"].get("tags")
    tags = [t.strip() for t in raw.split(",")]
    assert tags == ["ram vs storage", "what is ram", "phone memory explained"]
    assert YOUTUBE_CATEGORY_IDS["science & technology"] == "28"


def test_json_drop_publishes_end_to_end(tmp_path: Path):
    md = make_json_drop(tmp_path)
    data = json.loads(md.read_text())
    data["mock"] = {}
    md.write_text(json.dumps(data))
    result = publish_drop(md, force=True)
    state = result["state"]
    assert state.platforms["mock"].status == "published"
    assert len(state.platforms) == 4
    out = json.loads(md.read_text())
    assert out["youtube"]["title"].startswith("RAM vs Storage")
    assert out["published"]["mock"]["status"] == "published"
    assert "not authenticated" in out["published"]["instagram"]["error"].lower()
    from socialdrop.publisher import sync_folder_stats

    sync_folder_stats(tmp_path)
    out = json.loads(md.read_text())
    assert out["insights"]["metrics"]["mock"]["views"] > 0


def test_invalid_json_reported(tmp_path: Path):
    (tmp_path / "broken.mp4").write_bytes(b"x")
    bad = tmp_path / "broken.json"
    bad.write_text("{not json")
    errors = __import__("socialdrop.schema", fromlist=["validate_drop_file"]).validate_drop_file(bad)
    assert any("invalid JSON" in e for e in errors)
