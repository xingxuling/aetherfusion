"""Safe command runner — executes whitelisted commands inside the target
project directory with timeouts and captured output.

Blocked commands: rm, del, curl, wget, git push, npm install, pip install,
and any command not on the whitelist.
"""

import subprocess
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Whitelist — only these exact commands (or prefixes) are allowed
# ---------------------------------------------------------------------------
ALLOWED_COMMANDS: list[str] = [
    "npm run build",
    "npm test",
    "npm run test",
    "npm run lint",
    "npm run typecheck",
    "npx tsc --noEmit",
    "pytest",
    "python -m pytest",
]

# ---------------------------------------------------------------------------
# Blocklist — exact matches or substrings that are forbidden even if they
# happened to slip past the whitelist
# ---------------------------------------------------------------------------
BLOCKED_SUBSTRINGS: list[str] = [
    "rm ",
    "del ",
    "rmdir ",
    "curl ",
    "wget ",
    "git push",
    "npm install",
    "pip install",
    "npm i ",
    "yarn add",
    "&&",
    ";",
    "|",
    "`",
    "$(",
    "format",
    "shutdown",
    "reboot",
]

# Timeout per command (seconds)
COMMAND_TIMEOUT: float = 120.0

# Maximum output tail length to capture (characters)
OUTPUT_TAIL_LENGTH: int = 2000


def _is_command_allowed(command: str) -> tuple[bool, str]:
    """Check whether a command is on the whitelist and has no blocked substrings.

    Returns (allowed, reason).
    """
    cmd_lower = command.strip().lower()

    # Check blocked substrings first
    for blocked in BLOCKED_SUBSTRINGS:
        if blocked in cmd_lower:
            return False, f"Blocked: command contains forbidden pattern '{blocked}'"

    # Check against whitelist — must be an exact prefix match
    # (the command may have extra args after the whitelisted base, so we
    #  check prefix)
    for allowed in ALLOWED_COMMANDS:
        allowed_lower = allowed.lower()
        if cmd_lower == allowed_lower or cmd_lower.startswith(allowed_lower + " "):
            return True, ""

    return False, f"Blocked: command not in whitelist. Allowed: {', '.join(ALLOWED_COMMANDS)}"


def run_single_command(
    command: str,
    cwd: Path,
    timeout: float = COMMAND_TIMEOUT,
) -> dict[str, Any]:
    """Run a single whitelist-checked command in a subprocess.

    Args:
        command: The shell command string to execute.
        cwd: Working directory for the subprocess (must be inside target).
        timeout: Maximum allowed runtime in seconds.

    Returns:
        Result dict with keys:
        - command: original command string
        - status: passed / failed / skipped / timeout / blocked
        - exit_code: int or None
        - duration_ms: int
        - stdout_tail: last OUTPUT_TAIL_LENGTH chars of stdout
        - stderr_tail: last OUTPUT_TAIL_LENGTH chars of stderr
        - reason: human-readable reason (empty on success)
    """
    allowed, reason = _is_command_allowed(command)
    if not allowed:
        return {
            "command": command,
            "status": "blocked",
            "exit_code": None,
            "duration_ms": 0,
            "stdout_tail": "",
            "stderr_tail": "",
            "reason": reason,
        }

    # Resolve cwd to ensure it exists
    cwd_resolved = cwd.resolve()
    if not cwd_resolved.is_dir():
        return {
            "command": command,
            "status": "skipped",
            "exit_code": None,
            "duration_ms": 0,
            "stdout_tail": "",
            "stderr_tail": "",
            "reason": f"Target directory does not exist: {cwd_resolved}",
        }

    start = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd_resolved),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        duration_ms = int((time.perf_counter() - start) * 1000)

        stdout_tail = _tail(proc.stdout or "", OUTPUT_TAIL_LENGTH)
        stderr_tail = _tail(proc.stderr or "", OUTPUT_TAIL_LENGTH)

        if proc.returncode == 0:
            return {
                "command": command,
                "status": "passed",
                "exit_code": 0,
                "duration_ms": duration_ms,
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail,
                "reason": "",
            }
        else:
            reason_str = f"Command exited with code {proc.returncode}"
            # Check for common "not found" indicators
            if proc.returncode == 1 and ("not found" in stderr_tail.lower() or "not found" in stdout_tail.lower()):
                return {
                    "command": command,
                    "status": "skipped",
                    "exit_code": proc.returncode,
                    "duration_ms": duration_ms,
                    "stdout_tail": stdout_tail,
                    "stderr_tail": stderr_tail,
                    "reason": reason_str + " (command or tool not found)",
                }
            return {
                "command": command,
                "status": "failed",
                "exit_code": proc.returncode,
                "duration_ms": duration_ms,
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail,
                "reason": reason_str,
            }

    except subprocess.TimeoutExpired:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return {
            "command": command,
            "status": "timeout",
            "exit_code": None,
            "duration_ms": duration_ms,
            "stdout_tail": "",
            "stderr_tail": f"Command timed out after {timeout} seconds",
            "reason": f"Command timed out after {timeout}s",
        }
    except FileNotFoundError:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return {
            "command": command,
            "status": "skipped",
            "exit_code": None,
            "duration_ms": duration_ms,
            "stdout_tail": "",
            "stderr_tail": "Command not found — required tool may not be installed",
            "reason": "Command not found — required tool may not be installed",
        }
    except OSError as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return {
            "command": command,
            "status": "failed",
            "exit_code": None,
            "duration_ms": duration_ms,
            "stdout_tail": "",
            "stderr_tail": str(e),
            "reason": str(e),
        }


def run_commands(
    commands: list[str],
    target_path: Path,
    timeout: float = COMMAND_TIMEOUT,
) -> list[dict[str, Any]]:
    """Run a list of commands sequentially inside the target directory.

    Single command failure does NOT terminate the verify flow — all
    commands are attempted regardless of earlier results.

    Args:
        commands: List of shell command strings.
        target_path: Working directory for all commands.
        timeout: Per-command timeout in seconds.

    Returns:
        List of result dicts (see run_single_command).
    """
    results: list[dict[str, Any]] = []
    for cmd in commands:
        result = run_single_command(cmd, target_path, timeout=timeout)
        results.append(result)
    return results


def _tail(text: str, max_len: int) -> str:
    """Return the last max_len characters of text."""
    if len(text) <= max_len:
        return text
    return "...(truncated)...\n" + text[-max_len:]