import json

import pytest

from blackbox import cli


def test_demo_bundle_has_every_run_explained(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "DEMO", [("collision", 0), ("nominal", 0)])
    cli.build_demo(tmp_path / "data")
    idx = json.loads((tmp_path / "data" / "index.json").read_text())
    assert [r["scenario"] for r in idx["runs"]] == ["collision", "nominal"]
    for r in idx["runs"]:
        folder = tmp_path / "data" / r["id"]
        x = json.loads((folder / "explain.json").read_text())
        assert x["run"] == r["id"]
        assert (folder / "frames" / "0000.jpg").exists()


def test_eval_reports_accuracy():
    r = cli.evaluate(2)
    assert r["runs"] == 12
    assert r["accuracy"] >= 0.9


def test_verify_command(tmp_path, capsys):
    cli.main(["simulate", "wrong_object", "--seed", "1", "--out", str(tmp_path), "--no-frames"])
    run = tmp_path / "wrong_object-001"
    cli.main(["explain", str(run), "--backend", "rules"])
    try:
        cli.main(["verify", str(run / "explain.json")])
    except SystemExit as e:
        assert e.code == 0
    assert "VERIFIED" in capsys.readouterr().out


JSON_KEYS = {"format", "run", "run_sha256", "explanation", "verdict", "kept", "refuted", "evidence"}
VERDICT_KEYS = {"outcome", "headline", "symptom", "root", "chain", "failure_moment", "claims"}


@pytest.mark.parametrize("scenario,seed", [("collision", 3), ("slip_grip", 5)])
def test_explain_json_round_trips(tmp_path, capsys, scenario, seed):
    cli.main(["simulate", scenario, "--seed", str(seed), "--out", str(tmp_path), "--no-frames"])
    run = tmp_path / f"{scenario}-{seed:03d}"
    capsys.readouterr()
    cli.main(["explain", str(run), "--backend", "rules", "--json"])
    j = json.loads(capsys.readouterr().out)
    assert json.loads(json.dumps(j)) == j
    assert set(j) == JSON_KEYS and set(j["verdict"]) == VERDICT_KEYS
    assert j["format"] == cli.JSON_FORMAT and j["run"] == run.name

    x = json.loads((run / "explain.json").read_text())
    assert j == json.loads(json.dumps(cli.explain_summary(x, run / "explain.json")))
    assert j["evidence"] == x["evidence"]
    assert j["verdict"]["outcome"] == "failure" and j["verdict"]["root"] == x["cause"]["root"]
    assert {h["id"] for h in j["kept"]} == {n["id"] for n in x["hypotheses"] if n["status"] == "kept"}
    assert {h["id"] for h in j["refuted"]} == {n["id"] for n in x["hypotheses"] if n["status"] == "killed"}
    assert j["kept"] and j["refuted"]
    ids = {e["id"] for e in j["evidence"]}
    for h in j["kept"] + j["refuted"]:
        assert set(h["evidence"]) <= ids
    for c in j["verdict"]["claims"]:
        assert set(c["cites"]) <= ids


def test_explain_json_nominal_success(tmp_path, capsys):
    cli.main(["simulate", "nominal", "--out", str(tmp_path), "--no-frames"])
    run = tmp_path / "nominal-000"
    capsys.readouterr()
    cli.main(["explain", str(run), "--backend", "rules", "--json"])
    j = json.loads(capsys.readouterr().out)

    assert set(j) == JSON_KEYS and set(j["verdict"]) == VERDICT_KEYS
    assert j["format"] == "blackbox.explain-summary/1"
    assert j["verdict"]["outcome"] == "success"
    assert j["verdict"]["root"] is None
    assert j["verdict"]["failure_moment"] is None
    assert j["explanation"] == str(run / "explain.json")
    x = json.loads((run / "explain.json").read_text())
    assert x["outcome"] == "success"
    assert j["evidence"] == x["evidence"]
