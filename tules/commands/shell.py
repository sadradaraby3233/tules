"""Running a shell command inside the workspace."""

import subprocess
from typing import Any, Dict

from ..errors import TulesError
from ..models import Result
from ..registry import command, number, text

OUTPUT_LIMIT = 4000


@command("run", "Run a shell command in the workspace root")
def run(agent, payload: Dict[str, Any]) -> Result:
	if not agent.allow_shell:
		raise TulesError("Shell commands are disabled (started with --no-shell)")
	line = text(payload, "command")
	timeout = number(payload, "timeout", agent.shell_timeout)
	try:
		finished = subprocess.run(
			line, shell=True, capture_output=True, text=True,
			timeout=timeout, cwd=agent.workspace.root)
	except subprocess.TimeoutExpired:
		raise TulesError(f"Command timed out after {timeout}s") from None
	except OSError as exc:
		raise TulesError(f"Could not start the command: {exc}") from exc
	return Result(
		success=finished.returncode == 0,
		message=f"Exit code {finished.returncode}",
		details={
			"stdout": finished.stdout[-OUTPUT_LIMIT:],
			"stderr": finished.stderr[-OUTPUT_LIMIT:],
		},
	)
