import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tules.agent import Agent
from tules.workspace import Workspace

SAMPLE = """import os


def greet(name):
	return f"hello {name}"


class Widget:
	def build(self):
		return greet("widget")
"""


@pytest.fixture
def workspace(tmp_path) -> Workspace:
	(tmp_path / "sample.py").write_text(SAMPLE, encoding="utf-8")
	(tmp_path / "notes.md").write_text("# notes\nalpha\nbeta\n", encoding="utf-8")
	return Workspace(str(tmp_path))


@pytest.fixture
def agent(workspace) -> Agent:
	return Agent(root=str(workspace.root))
