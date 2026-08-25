"""Bash and PowerShell execution inside the workspace."""

import shutil
import subprocess
from typing import Any, Dict, List

from ..errors import TulesError
from ..models import Result
from ..registry import command, number, text

OUTPUT_LIMIT = 30_000
MAX_TIMEOUT = 600


def _execute(agent, payload: Dict[str, Any], argv: List[str], shell_name: str) -> Result:
	if not agent.allow_shell:
		raise TulesError("Shell commands are disabled (started with --no-shell)")
	timeout = number(payload, "timeout", agent.shell_timeout)
	if timeout < 1 or timeout > MAX_TIMEOUT:
		raise TulesError(f"'timeout' must be between 1 and {MAX_TIMEOUT} seconds")
	if payload.get("run_in_background"):
		raise TulesError(
			"Background execution is not available in clipboard mode; run a finite command instead"
		)
	try:
		finished = subprocess.run(
			argv,
			capture_output=True,
			text=True,
			errors="replace",
			timeout=timeout,
			cwd=agent.workspace.root,
		)
	except subprocess.TimeoutExpired as exc:
		raise TulesError(
			f"{shell_name} command timed out after {timeout}s",
			stdout=(exc.stdout or "")[-OUTPUT_LIMIT:],
			stderr=(exc.stderr or "")[-OUTPUT_LIMIT:],
		) from None
	except OSError as exc:
		raise TulesError(f"Could not start {shell_name}: {exc}") from exc
	return Result(
		success=finished.returncode == 0,
		message=f"{shell_name} exit code {finished.returncode}",
		details={
			"stdout": finished.stdout[-OUTPUT_LIMIT:],
			"stderr": finished.stderr[-OUTPUT_LIMIT:],
			"exit_code": finished.returncode,
			"shell": shell_name,
			"description": payload.get("description", ""),
			"truncated": len(finished.stdout) > OUTPUT_LIMIT or len(finished.stderr) > OUTPUT_LIMIT,
		},
	)


@command("bash", "Execute a Bash command in the workspace")
def bash(agent, payload: Dict[str, Any]) -> Result:
	line = text(payload, "command")
	executable = shutil.which("bash")
	if not executable:
		raise TulesError("Bash is not installed or is not on PATH")
	return _execute(agent, payload, [executable, "-lc", line], "Bash")


@command("powershell", "Execute a PowerShell command in the workspace")
def powershell(agent, payload: Dict[str, Any]) -> Result:
	line = text(payload, "command")
	executable = shutil.which("pwsh") or shutil.which("powershell")
	if not executable:
		raise TulesError(
			"PowerShell is not installed or is not on PATH. "
			"Install PowerShell 7 (pwsh) to use this tool.")
	return _execute(
		agent,
		payload,
		[executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", line],
		"PowerShell",
	)


@command("run", "Backward-compatible alias for Bash execution")
def run(agent, payload: Dict[str, Any]) -> Result:
	"""Backward-compatible shell command; Bash is deterministic on this platform."""
	return bash(agent, payload)
