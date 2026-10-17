"""The LLM backend against a fake OpenAI-compatible server: no network, no paid calls."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from blackbox.agent import KEPT, LLMBackend, explain, parse_json, LLMError
from conftest import run


class Fake:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        fake = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
                if not fake.replies:
                    self.send_response(500)
                    self.end_headers()
                    return
                reply = fake.replies.pop(0)
                if reply == 500:
                    self.send_response(500)
                    self.end_headers()
                    return
                out = {"choices": [{"message": {"role": "assistant", "content": reply}}]}
                data = json.dumps(out).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_port}/v1"

    def close(self):
        self.srv.shutdown()


def backend(fake):
    return LLMBackend(base_url=fake.url, api_key="test-key", model="nvidia/test-nemotron", timeout=5)


def test_llm_picks_checks_and_custom_threshold_and_bad_ids_are_rejected(control):
    round1 = json.dumps({"run": [{"check": "drop", "why": "bottle missing from tray"}, {"check": "collision", "why": "rule out"},
                                 {"check": "teleport", "why": "made up"}],
                         "custom": [{"statement": "grip current collapsed while carrying", "channel": "gripper_current", "op": "<", "value": 0.15, "t0": 6, "t1": 12, "why": "slip signature"}]})
    round2 = "<think>low force or rushing?</think>" + json.dumps({"run": [{"check": "drop.low_grip_force", "why": "heavy bottle"}]})
    round3 = json.dumps({"run": [{"check": "drop.low_grip_force.config_change", "why": "who set it"}]})
    fake = Fake([round1, round2, round3, 500])  # the verdict call fails -> rules writer
    try:
        x = explain(run("slip_grip", 0), backend(fake), [control])
    finally:
        fake.close()
    ids = [h["id"] for h in x["hypotheses"]]
    assert ids[:3] == ["goal.met", "drop", "collision"]
    assert "teleport" not in ids and "drop.aggressive_motion" not in ids  # the model did not pick it
    custom = next(h for h in x["hypotheses"] if h["id"].startswith("custom."))
    assert custom["status"] == KEPT and custom["custom"]["channel"] == "gripper_current"
    assert x["cause"]["root"] == "drop.low_grip_force"
    assert x["backend"] == {"name": "llm", "model": "nvidia/test-nemotron", "writer": "rules"}
    assert any(t["step"] == "reject" and "teleport" in t["msg"] for t in x["trace"])
    assert fake.requests[0]["path"] == "/v1/chat/completions"
    assert fake.requests[0]["auth"] == "Bearer test-key"
    assert fake.requests[0]["body"]["model"] == "nvidia/test-nemotron"


def test_llm_verdict_claims_without_real_evidence_are_dropped(control):
    log = run("collision", 0)
    # same order as the rules backend, so evidence ids line up with the reference run below
    picks = json.dumps({"run": [{"check": c, "why": ""} for c in ("timeout", "collision", "drop", "wrong_object", "empty_grasp")]})
    picks2 = json.dumps({"run": [{"check": c, "why": ""} for c in ("collision.unmodeled_obstacle", "collision.known_obstacle", "collision.sensor_glitch")]})

    def verdict_for(x):
        return json.dumps({"headline": "Hit an unmapped cereal box.", "claims": [
            {"kind": "finding", "text": "The base stalled against something.", "cites": [kept_ev]},
            {"kind": "cause", "text": "Gremlins.", "cites": ["E999"]},
            {"kind": "cause", "text": "Rests on a killed hypothesis.", "cites": [x]},
        ]})

    # find an evidence id owned only by a killed node, from a rules run on the same log
    ref = explain(log, None, [control])
    killed_only = next(e for h in ref["hypotheses"] if h["status"] == "killed" for e in h["evidence"]
                       if all(e not in k["evidence"] for k in ref["hypotheses"] if k["status"] == "kept"))
    kept_ev = next(h["evidence"][0] for h in ref["hypotheses"] if h["id"] == "collision")
    fake = Fake([picks, picks2, verdict_for(killed_only)])
    try:
        x = explain(log, backend(fake), [control])
    finally:
        fake.close()
    assert x["backend"]["writer"] == "llm"
    assert x["headline"] == "Hit an unmapped cereal box."
    texts = [c["text"] for c in x["claims"]]
    assert texts == ["The base stalled against something."]
    assert sum("claim dropped" in t["msg"] for t in x["trace"]) == 2


def test_llm_unreachable_falls_back_to_rules(control):
    b = LLMBackend(base_url="http://127.0.0.1:9/v1", api_key="x", timeout=1)
    x = explain(run("wrong_object", 0), b, [control])
    assert x["cause"]["root"] == "wrong_object.perception_confusion"
    assert x["backend"]["writer"] == "rules"
    assert any(t["step"] == "fallback" for t in x["trace"])


def test_parse_json_tolerates_fences_and_thinking():
    assert parse_json('<think>{"no": 1}</think>\n```json\n{"a": 2}\n```') == {"a": 2}
    with pytest.raises(LLMError):
        parse_json("no json here")


def test_env_defaults_point_at_nemotron(monkeypatch):
    for k in ("BLACKBOX_LLM_BASE_URL", "BLACKBOX_LLM_MODEL", "BLACKBOX_LLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "nv-test")
    b = LLMBackend()
    assert b.base_url == "https://integrate.api.nvidia.com/v1"
    assert b.model.startswith("nvidia/nemotron")
    assert b.api_key == "nv-test"
