"""A light and dark pair must merge as it did before the merge took more than
two builds: the same themes and swaps, the same counts and the same pixels."""

import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
from snapshot_two_build import SNAPSHOT, paths, snapshot  # noqa: E402

EXPECTED = json.loads(SNAPSHOT.read_text())


@pytest.mark.parametrize("pair", sorted(EXPECTED))
def test_two_builds_merge_as_they_did(pair):
    assert snapshot(*paths(pair)) == EXPECTED[pair]
