"""Bash and PowerShell execution inside the workspace."""

import os
import shutil
import signal
import subprocess
from contextlib import suppress
from typing import Any, Dict, List, Tuple

from ..errors import TulesError
from ..models import Result
from ..registry import command, number, text

OUTPUT_LIMIT = 30_000
MAX_TIMEOUT = 600
# How long a killed process group gets to die before we stop waiting for it.
REAP_SECONDS = 5
POSIX = os.name == "posix"


def _spawn(argv: List[str], cwd) -> subprocess.Popen:
	"""Start the command in its own process group, so it can be killed whole."""
	return subprocess.Popen(
		argv,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True,
		errors="replace",
		cwd=cwd,
		start_new_session=POSIX,
	)


def _terminate(process: subprocess.Popen) -> None:
	"""Kill the whole process tree: a shell's children outlive the shell."""
	if POSIX:
		with suppress(OSError, ProcessLookupError):
			os.killpg(os.getpgid(process.pid), signal.SIGKILL)
	with suppress(OSError):
		process.kill()


def _communicate(process: subprocess.Popen, timeout: int) -> Tuple[str, str, int]:
	"""Collect output, or kill the tree and raise when it overruns the timeout."""
	try:
		stdout, stderr = process.communicate(timeout=timeout)
	except subprocess.TimeoutExpired:
		_terminate(process)
		try:
			# The pipes stay open while any grandchild holds them, so this is
			# bounded: whatever has not arrived by now is not coming.
			stdout, stderr = process.communicate(timeout=REAP_SECONDS)
		except subprocess.TimeoutExpired:
			stdout, stderr = "", ""
		raise TulesError(
			f"Command timed out after {timeout}s and its process group was killed",
			stdout=(stdout or "")[-OUTPUT_LIMIT:],
			stderr=(stderr or "")[-OUTPUT_LIMIT:],
			timed_out=True,
		) from None
	return stdout or "", stderr or "", process.returncode


def _execute(agent, payload: Dict[str, Any], argv: List[str], shell_name: str) -> Result:
	if not agent.allow_shell:
		raise TulesError("Shell commands are disabled (started with --no-shell)")
	timeout = number(payload, "timeout", agent.shell_timeout)
	if not 1 <= timeout <= MAX_TIMEOUT:
		raise TulesError(f"'timeout' must be between 1 and {MAX_TIMEOUT} seconds")
	if payload.get("run_in_background"):
		raise TulesError(
			"Background execution is not available in clipboard mode; run a finite command instead"
		)
	try:
		process = _spawn(argv, agent.workspace.root)
	except OSError as exc:
		raise TulesError(f"Could not start {shell_name}: {exc}") from exc
	try:
		stdout, stderr, code = _communicate(process, timeout)
	except TulesError as exc:
		exc.message = f"{shell_name} {exc.message[0].lower()}{exc.message[1:]}"
		raise
	return Result(
		success=code == 0,
		message=f"{shell_name} exit code {code}",
		details={
			"stdout": stdout[-OUTPUT_LIMIT:],
			"stderr": stderr[-OUTPUT_LIMIT:],
			"exit_code": code,
			"shell": shell_name,
			"description": payload.get("description", ""),
			"truncated": len(stdout) > OUTPUT_LIMIT or len(stderr) > OUTPUT_LIMIT,
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
			"Install PowerShell 7 (pwsh) to use this tool."
		)
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
