"""Arm model for the simulated Thenar / SO-101 style arm.

The joint order, home pose, speed caps and 25 Hz control rate come from REACH
(`../reach-amazon/reach/arm.py`), so a log recorded on the real arm and one from
this simulator line up channel for channel:

    [base_pan, shoulder, elbow, wrist_flex, wrist_roll, gripper]   (degrees)

Geometry convention used here (side view, r = horizontal distance from the base axis):
  shoulder    upper-arm angle from vertical, + leans forward
  elbow       forearm angle relative to the upper arm, 0 = forearm at right angles to it
  wrist_flex  gripper angle relative to the forearm
The gripper points straight down when shoulder + elbow + wrist_flex + 90 = 180.
"""

from __future__ import annotations

import math

import numpy as np

JOINTS = ["base", "shoulder", "elbow", "wrist_flex", "wrist_roll", "gripper"]
# From reach/arm.py, except wrist_flex gets ±90 so the gripper can point down at the edge of reach.
LO = np.array([-85, -80, -80, -90, -85, 0], float)
HI = np.array([85, 80, 80, 90, 85, 70], float)
HOME = np.array([0, -25, 35, 0, 0, 20], float)
VMAX = np.array([60, 40, 50, 80, 90, 120], float)  # deg/s per joint (reach/arm.py)
RATE = 25.0

BASE_H, L1, L2, L3 = 0.10, 0.116, 0.135, 0.10  # metres: shoulder height, upper arm, forearm, wrist to fingertip centre
GRIP_W_MAX = 0.08  # finger gap at full opening (70 deg)
REACH = L1 + L2  # max shoulder-to-wrist distance


def opening_to_width(deg: float) -> float:
    return GRIP_W_MAX * float(deg) / HI[5]


def width_to_opening(w: float) -> float:
    return float(w) / GRIP_W_MAX * HI[5]


def chain(q) -> dict[str, np.ndarray]:
    """Joint positions in metres (x forward, y left, z up) for pose q."""
    b = math.radians(q[0])
    a1 = math.radians(q[1])
    a2 = math.radians(q[1] + q[2] + 90)
    a3 = math.radians(q[1] + q[2] + q[3] + 90)
    s = (0.0, BASE_H)
    e = (s[0] + L1 * math.sin(a1), s[1] + L1 * math.cos(a1))
    w = (e[0] + L2 * math.sin(a2), e[1] + L2 * math.cos(a2))
    t = (w[0] + L3 * math.sin(a3), w[1] + L3 * math.cos(a3))
    cb, sb = math.cos(b), math.sin(b)

    def p(rz):
        return np.array([rz[0] * cb, rz[0] * sb, rz[1]])

    return {"base": np.zeros(3), "shoulder": p(s), "elbow": p(e), "wrist": p(w), "tip": p(t)}


def fk(q) -> np.ndarray:
    return chain(q)["tip"]


def ik(x: float, y: float, z: float, gripper: float = 20.0, roll: float = 0.0) -> tuple[np.ndarray, bool]:
    """Pose that puts the fingertip centre at (x, y, z) pointing straight down.

    Returns (pose, reachable). An unreachable point gets the closest pose along the same
    bearing (arm stretched out), clamped to joint limits, with reachable=False."""
    base = math.degrees(math.atan2(y, x))
    r = math.hypot(x, y)
    wr, wz = r, z + L3
    dx, dz = wr, wz - BASE_H
    d = math.hypot(dx, dz)
    ok = True
    if d > REACH - 1e-4:
        ok = False
        k = (REACH - 1e-4) / d
        dx, dz, d = dx * k, dz * k, REACH - 1e-4
        wr, wz = dx, dz + BASE_H
    phi = math.atan2(dx, dz)
    alpha = math.acos(max(-1.0, min(1.0, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
    a1 = phi - alpha  # elbow up
    er, ez = L1 * math.sin(a1), BASE_H + L1 * math.cos(a1)
    a2 = math.atan2(wr - er, wz - ez)
    q1 = math.degrees(a1)
    q2 = math.degrees(a2) - q1 - 90
    q3 = 180 - math.degrees(a2)
    q = np.array([base, q1, q2, q3, roll, gripper], float)
    qc = np.clip(q, LO, HI)
    if np.any(np.abs(qc - q) > 0.5):
        ok = False
    return qc, ok


def max_reach_at(z: float) -> float:
    """Largest horizontal distance from the base axis the fingertip can reach at height z, pointing down."""
    dz = z + L3 - BASE_H
    return math.sqrt(max(0.0, REACH * REACH - dz * dz))
