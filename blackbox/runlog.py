"""The BLACKBOX run log: one robot episode as a folder.

    <run>/run.json      everything below except the pixels
    <run>/frames/*.jpg  camera frames, named in run.json

run.json (format "blackbox.run/1"):
  id, robot          arm model: joint names, limits, link lengths, max reach
  goal               {text, target (object label), destination (zone), deadline_s}
  rate_hz            telemetry rate
  series             columnar telemetry, one row per tick:
                       t [s], q / q_cmd [deg x6 measured / commanded], current [A x5 joint motors],
                       gripper / gripper_cmd [deg opening], gripper_current [A], tcp [m xyz, from the controller's FK]
  camera             {rate_hz, frames: [{t, file}]}
  tracks             perception output per tracked object:
                       {track_id: {size [m], color, xyz [[t,x,y,z]], labels [[t,label,conf,runner_up,runner_conf]]}}
  zones              named regions on the table: {name: {center [x,y], size [w,d]}}
  events             controller events [{t, kind, msg, data}]
  config             controller settings in force for this run
  objects_db         known properties per object label (mass, friction)
  records            other data sources about the robot (maintenance log, config changelog)
  meta               {simulated, seed, scenario, truth}; `truth` is simulator ground truth and
                     the explainer never reads it (tests strip it to prove that).
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

FORMAT = "blackbox.run/1"
REQUIRED = ["id", "robot", "goal", "rate_hz", "series", "camera", "tracks", "zones", "events", "config"]
SERIES = {"t": 1, "q": 6, "q_cmd": 6, "current": 5, "gripper": 1, "gripper_cmd": 1, "gripper_current": 1, "tcp": 3}


class LogError(ValueError):
    pass


@dataclass
class RunLog:
    data: dict
    root: Path | None = None
    _arr: dict = field(default_factory=dict, repr=False)

    # ---- access ---------------------------------------------------------------------------
    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def goal(self) -> dict:
        return self.data["goal"]

    @property
    def config(self) -> dict:
        return self.data["config"]

    @property
    def events(self) -> list[dict]:
        return self.data["events"]

    @property
    def tracks(self) -> dict:
        return self.data["tracks"]

    @property
    def zones(self) -> dict:
        return self.data["zones"]

    @property
    def records(self) -> list[dict]:
        return self.data.get("records", [])

    @property
    def objects_db(self) -> dict:
        return self.data.get("objects_db", {})

    def s(self, name: str) -> np.ndarray:
        """A telemetry series as a numpy array (cached)."""
        if name not in self._arr:
            self._arr[name] = np.asarray(self.data["series"][name], float)
        return self._arr[name]

    @property
    def t(self) -> np.ndarray:
        return self.s("t")

    @property
    def duration(self) -> float:
        return float(self.t[-1]) if len(self.t) else 0.0

    def idx(self, t: float) -> int:
        return int(np.clip(np.searchsorted(self.t, t), 0, len(self.t) - 1))

    def track_xyz(self, tid: str) -> np.ndarray:
        return np.asarray(self.tracks[tid]["xyz"], float)

    def frames(self) -> list[dict]:
        return self.data["camera"]["frames"]

    def frame_at(self, t: float) -> dict | None:
        fr = self.frames()
        if not fr:
            return None
        return min(fr, key=lambda f: abs(f["t"] - t))

    def without_truth(self) -> "RunLog":
        d = copy.deepcopy(self.data)
        d.get("meta", {}).pop("truth", None)
        return RunLog(d, self.root)

    def sha256(self) -> str:
        """Hash of the log content the explainer can see (ground truth excluded)."""
        d = copy.deepcopy(self.data)
        d.get("meta", {}).pop("truth", None)
        return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    # ---- io -------------------------------------------------------------------------------
    def save(self, folder: Path) -> Path:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "run.json").write_text(json.dumps(self.data, separators=(",", ":")))
        self.root = folder
        return folder / "run.json"

    @classmethod
    def load(cls, path: Path | str) -> "RunLog":
        p = Path(path)
        if p.is_dir():
            p = p / "run.json"
        try:
            data = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError) as e:
            raise LogError(f"cannot read {p}: {e}") from e
        log = cls(data, p.parent)
        validate(log)
        return log


def validate(log: RunLog) -> None:
    d = log.data
    if d.get("format") != FORMAT:
        raise LogError(f"not a {FORMAT} log (format={d.get('format')!r})")
    missing = [k for k in REQUIRED if k not in d]
    if missing:
        raise LogError(f"missing fields: {', '.join(missing)}")
    n = len(d["series"].get("t", []))
    if n < 2:
        raise LogError("series.t needs at least two samples")
    for name, width in SERIES.items():
        col = d["series"].get(name)
        if col is None:
            raise LogError(f"series.{name} missing")
        if len(col) != n:
            raise LogError(f"series.{name} has {len(col)} rows, expected {n}")
        if width > 1 and any(len(r) != width for r in col):
            raise LogError(f"series.{name} rows must have {width} values")
    t = np.asarray(d["series"]["t"], float)
    if np.any(np.diff(t) <= 0):
        raise LogError("series.t must be strictly increasing")
    for k in ("target", "destination", "deadline_s"):
        if k not in d["goal"]:
            raise LogError(f"goal.{k} missing")
    if d["goal"]["destination"] not in d["zones"]:
        raise LogError(f"goal destination {d['goal']['destination']!r} is not a zone")
