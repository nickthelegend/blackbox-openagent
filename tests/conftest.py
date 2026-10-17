import functools

import pytest

from blackbox.sim import simulate


@functools.lru_cache(maxsize=None)
def run(name: str, seed: int = 0, render: bool = False):
    return simulate(name, seed, render=render)


@pytest.fixture(scope="session")
def control():
    return run("nominal", 100)
