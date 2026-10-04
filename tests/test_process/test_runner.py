import sys
import subprocess

import pytest

from flashflow.process import CommandExecutionError, ProcessRunner


def test_runner_uses_argument_list_and_reports_success_output(tmp_path):
    calls = []

    def executor(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "done\n", "")

    result = ProcessRunner(executor).run(["python", "-c", "print('hello world')"], cwd=tmp_path)

    assert result.stdout == "done\n"
    assert calls[0][0] == ["python", "-c", "print('hello world')"]
    assert calls[0][1]["cwd"] == tmp_path
    assert calls[0][1]["check"] is False


def test_runner_includes_subprocess_stderr_in_failure():
    def executor(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", "upload rejected")

    with pytest.raises(CommandExecutionError, match="upload rejected"):
        ProcessRunner(executor).run(["python", "-m", "twine", "upload", "artifact.whl"])


def test_runner_preserves_real_subprocess_diagnostics():
    command = [
        sys.executable,
        "-c",
        "import sys; print('specific rejection', file=sys.stderr); sys.exit(1)",
    ]

    with pytest.raises(CommandExecutionError, match="specific rejection"):
        ProcessRunner().run(command)


def test_runner_reports_command_start_failure():
    def executor(command, **kwargs):
        raise FileNotFoundError("python executable missing")

    with pytest.raises(CommandExecutionError, match="Could not start command"):
        ProcessRunner(executor).run(["python", "--version"])


@pytest.mark.parametrize("command", [[], ["python", 1]])
def test_runner_rejects_invalid_command_sequences(command):
    with pytest.raises(ValueError, match="sequences of strings"):
        ProcessRunner().run(command)
