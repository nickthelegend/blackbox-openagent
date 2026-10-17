import json

import pytest

from blackbox.runlog import LogError, RunLog
from blackbox.sim import save_run, simulate


def test_roundtrip_with_frames(tmp_path):
    log = simulate("collision", 1)
    folder = save_run(log, tmp_path / log.id)
    back = RunLog.load(folder)
    assert back.id == log.id
    assert back.sha256() == log.sha256()
    frames = back.frames()
    assert frames and all((folder / f["file"]).exists() for f in frames)
    assert (folder / frames[0]["file"]).read_bytes()[:2] == b"\xff\xd8"  # JPEG


def test_hash_ignores_ground_truth():
    log = simulate("timeout", 0, render=False)
    stripped = log.without_truth()
    assert "truth" not in stripped.data["meta"]
    assert stripped.sha256() == log.sha256()


@pytest.mark.parametrize("breakage, msg", [
    (lambda d: d.pop("goal"), "missing fields"),
    (lambda d: d["series"]["q"].pop(), "rows"),
    (lambda d: d["series"]["t"].__setitem__(3, 0.0), "increasing"),
    (lambda d: d["goal"].__setitem__("destination", "shelf"), "not a zone"),
    (lambda d: d.__setitem__("format", "other/1"), "not a blackbox.run/1"),
])
def test_validation_rejects_broken_logs(tmp_path, breakage, msg):
    log = simulate("nominal", 0, render=False)
    d = json.loads(json.dumps(log.data))
    breakage(d)
    (tmp_path / "run.json").write_text(json.dumps(d))
    with pytest.raises(LogError, match=msg):
        RunLog.load(tmp_path)
