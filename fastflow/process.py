"""Shared, shell-free subprocess execution for fastflow commands."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path


class CommandExecutionError(RuntimeError):
    """A subprocess could not be started or exited unsuccessfully."""

    def __init__(
        self,
        command: Sequence[str],
        returncode: int | None,
        stdout: str | None = None,
        stderr: str | None = None,
        cause: OSError | subprocess.CalledProcessError | None = None,
    ) -> None:
        self.command = tuple(command)
        self.returncode = returncode
        self.stdout = stdout or ""
        self.stderr = stderr or ""

        command_text = subprocess.list2cmdline(self.command)
        if returncode is None:
            message = f"Could not start command ({command_text}): {cause}"
        else:
            message = f"Command ({command_text}) exited with status {returncode}."
            if self.stdout.strip():
                message += f"\nstdout:\n{self.stdout.strip()}"
            if self.stderr.strip():
                message += f"\nstderr:\n{self.stderr.strip()}"
        super().__init__(message)


CommandExecutor = Callable[..., subprocess.CompletedProcess[str]]

class ProcessRunner:
    """Run argument-list commands and surface complete, actionable failures."""

    def __init__(self, executor: CommandExecutor = subprocess.run) -> None:
        self._executor = executor

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path | str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if not command or any(not isinstance(part, str) for part in command):
            raise ValueError("Commands must be non-empty sequences of strings.")

        try:
            result = self._executor(
                list(command),
                cwd=cwd,
                check=False,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise CommandExecutionError(
                command,
                exc.returncode,
                stdout=exc.stdout,
                stderr=exc.stderr,
                cause=exc,
            ) from exc
        except OSError as exc:
            raise CommandExecutionError(command, None, cause=exc) from exc

        if result.returncode:
            raise CommandExecutionError(
                command,
                result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        return result
