import subprocess

import pytest

from fastflow.commands.project import Configuration, ProjectError, ProjectManager
from fastflow.process import ProcessRunner


class FakeExecutor:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if self.fail:
            raise OSError("simulated venv failure")
        return subprocess.CompletedProcess(command, 0, "", "")


def test_create_generates_scaffold_and_creates_virtual_environment(tmp_path):
    executor = FakeExecutor()
    manager = ProjectManager(
        "My Example Project",
        project_dir=tmp_path,
        runner=ProcessRunner(executor),
    )

    created = manager.create()

    assert {path.name for path in created} == {
        ".gitignore",
        "README.md",
        "LICENSE",
        "pyproject.toml",
        ".venv",
    }
    assert (tmp_path / "README.md").read_text(encoding="utf-8").startswith(
        "# My Example Project"
    )
    assert "*.egg-info/" in (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert executor.calls[0][0][-3:] == [
        str(tmp_path / ".venv"),
        "--prompt",
        "My-Example-Project-dev-venv",
    ]
    assert executor.calls[0][1]["cwd"] == tmp_path


def test_create_respects_disabled_features(tmp_path):
    config = Configuration(
        create_venv=False,
        create_gitignore=False,
        create_pyproject_toml=True,
        create_readme=False,
        create_license=False,
    )

    created = ProjectManager("minimal", config, tmp_path).create()

    assert [path.name for path in created] == ["pyproject.toml"]
    assert (tmp_path / "pyproject.toml").is_file()
    assert not (tmp_path / ".venv").exists()
    assert not (tmp_path / "README.md").exists()
    assert not (tmp_path / "LICENSE").exists()


def test_create_refuses_to_overwrite_existing_content(tmp_path):
    existing = tmp_path / "README.md"
    existing.write_text("user content", encoding="utf-8")

    with pytest.raises(ProjectError, match="Refusing to overwrite"):
        ProjectManager("demo", project_dir=tmp_path).create()

    assert existing.read_text(encoding="utf-8") == "user content"
    assert not (tmp_path / "pyproject.toml").exists()


def test_venv_failure_rolls_back_only_files_created_by_this_run(tmp_path):
    executor = FakeExecutor(fail=True)
    existing = tmp_path / "notes.txt"
    existing.write_text("keep", encoding="utf-8")
    manager = ProjectManager(
        "demo",
        project_dir=tmp_path,
        runner=ProcessRunner(executor),
    )

    with pytest.raises(ProjectError, match="Project creation failed"):
        manager.create()

    assert list(tmp_path.iterdir()) == [existing]
    assert existing.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("name", ["", "../escape", "bad/name", "line\nbreak"])
def test_project_name_rejects_empty_or_path_like_values(tmp_path, name):
    with pytest.raises(ProjectError, match="Project name"):
        ProjectManager(name, project_dir=tmp_path)
