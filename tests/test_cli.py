import json

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
