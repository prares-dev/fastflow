import subprocess
from pathlib import Path

import pytest

from fastflow.commands.release import ReleaseError, ReleaseManager
from fastflow.process import ProcessRunner


def make_project(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "1.2.3"\n',
        encoding="utf-8",
    )


class FakeRunner:
    def __init__(
        self,
        project_dir=None,
        fail_command=None,
        dirty=False,
        produce_artifact=True,
    ):
        self.calls = []
        self.project_dir = project_dir
        self.original_pyproject = (
            (Path(project_dir) / "pyproject.toml").read_text(encoding="utf-8")
            if project_dir is not None
            else None
        )
        self.fail_command = fail_command
        self.dirty = dirty
        self.produce_artifact = produce_artifact
        self.uploaded_artifacts = []
        self.head_queries = 0
        self.head_changes = False
        self.build_cwd = None
        self.build_version = None

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        if command[0:3] == ["git", "branch", "--show-current"]:
            return subprocess.CompletedProcess(command, 0, "main\n", "")
        if command[0:3] == ["git", "status", "--porcelain"]:
            return subprocess.CompletedProcess(command, 0, " M file.py\n" if self.dirty else "", "")
        if command == ["git", "rev-parse", "HEAD"]:
            self.head_queries += 1
            if self.head_queries == 1:
                commit = "parent"
            elif self.head_changes and self.head_queries == 3:
                commit = "unrelated"
            else:
                commit = "release"
            return subprocess.CompletedProcess(command, 0, f"{commit}\n", "")
        if command[1:3] == ["-m", "build"]:
            self.build_cwd = Path(kwargs["cwd"])
            self.build_version = (
                self.build_cwd / "pyproject.toml"
            ).read_text(encoding="utf-8")
            egg_info = Path(kwargs["cwd"]) / "demo.egg-info"
            egg_info.mkdir()
            if self.produce_artifact:
                output_dir = Path(command[command.index("--outdir") + 1])
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "demo-1.2.4.tar.gz").write_bytes(b"archive")
        if command[1:3] == ["-m", "twine"]:
            self.uploaded_artifacts = [Path(path) for path in command[4:]]
        if self.fail_command == "build" and command[1:3] == ["-m", "build"]:
            raise subprocess.CalledProcessError(1, command, stderr="simulated failure")
        if self.fail_command == "twine" and command[1:3] == ["-m", "twine"]:
            raise subprocess.CalledProcessError(1, command, stderr="simulated failure")
        if self.fail_command == "commit" and command[:2] == ["git", "commit"]:
            raise subprocess.CalledProcessError(1, command, stderr="simulated failure")
        if self.fail_command == "add" and command[:2] == ["git", "add"]:
            raise subprocess.CalledProcessError(1, command, stderr="simulated failure")
        if command[:3] == ["git", "reset", "--hard"]:
            if self.project_dir is not None:
                (Path(self.project_dir) / "pyproject.toml").write_text(
                    self.original_pyproject,
                    encoding="utf-8",
                )
        return subprocess.CompletedProcess(command, 0, "", "")


def test_release_builds_commits_uploads_then_offers_git_publication(tmp_path):
    make_project(tmp_path)
    egg_info = tmp_path / "old.egg-info"
    egg_info.mkdir()
    (egg_info / "keep.txt").write_text("preserve", encoding="utf-8")
    runner = FakeRunner(project_dir=tmp_path)
    answers = iter([True, True])
    manager = ReleaseManager(
        "1.2.4",
        tmp_path,
        ProcessRunner(runner),
        lambda _: next(answers),
    )

    manager.release()

    calls = runner.calls
    build_index = next(i for i, call in enumerate(calls) if call[1:3] == ["-m", "build"])
    commit_index = calls.index(["git", "commit", "-m", "Release v1.2.4"])
    upload_index = next(i for i, call in enumerate(calls) if call[1:3] == ["-m", "twine"])
    push_index = calls.index(["git", "push"])
    tag_index = calls.index(["git", "tag", "v1.2.4"])
    tag_push_index = calls.index(["git", "push", "origin", "v1.2.4"])
    assert build_index < commit_index < upload_index < push_index < tag_index < tag_push_index
    assert runner.uploaded_artifacts[0].name == "demo-1.2.4.tar.gz"
    assert not runner.uploaded_artifacts[0].exists()
    assert runner.build_cwd != tmp_path
    assert 'version = "1.2.4"' in runner.build_version
    assert (egg_info / "keep.txt").read_text(encoding="utf-8") == "preserve"
    assert not (tmp_path / "demo.egg-info").exists()
    assert 'version = "1.2.4"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")


def test_build_failure_restores_version_and_does_not_commit_or_publish(tmp_path):
    make_project(tmp_path)
    original = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    runner = FakeRunner(project_dir=tmp_path, fail_command="build")
    manager = ReleaseManager(
        "1.2.4",
        tmp_path,
        ProcessRunner(runner),
        lambda _: pytest.fail("unexpected prompt"),
    )

    with pytest.raises(ReleaseError, match="Build failed"):
        manager.release()

    assert (tmp_path / "pyproject.toml").read_text(encoding="utf-8") == original
    assert not any(call[:2] == ["git", "commit"] for call in runner.calls)
    assert not any(call[1:3] == ["-m", "twine"] for call in runner.calls)


def test_build_without_artifacts_restores_version_and_does_not_commit(tmp_path):
    make_project(tmp_path)
    original = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    runner = FakeRunner(project_dir=tmp_path, produce_artifact=False)
    manager = ReleaseManager(
        "1.2.4",
        tmp_path,
        ProcessRunner(runner),
        lambda _: pytest.fail("unexpected prompt"),
    )

    with pytest.raises(ReleaseError, match="produced no distribution files"):
        manager.release()

    assert (tmp_path / "pyproject.toml").read_text(encoding="utf-8") == original
    assert not any(call[:2] == ["git", "commit"] for call in runner.calls)


def test_commit_failure_restores_version_and_unstages_project_file(tmp_path):
    make_project(tmp_path)
    original = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    runner = FakeRunner(project_dir=tmp_path, fail_command="commit")
    manager = ReleaseManager(
        "1.2.4",
        tmp_path,
        ProcessRunner(runner),
        lambda _: pytest.fail("unexpected prompt"),
    )

    with pytest.raises(ReleaseError, match="Local release commit failed"):
        manager.release()

    assert (tmp_path / "pyproject.toml").read_text(encoding="utf-8") == original
    assert ["git", "restore", "--staged", "--", "pyproject.toml"] in runner.calls
    assert not any(call[1:3] == ["-m", "twine"] for call in runner.calls)


def test_git_add_failure_also_restores_project_version(tmp_path):
    make_project(tmp_path)
    original = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    runner = FakeRunner(project_dir=tmp_path, fail_command="add")
    manager = ReleaseManager(
        "1.2.4",
        tmp_path,
        ProcessRunner(runner),
        lambda _: pytest.fail("unexpected prompt"),
    )

    with pytest.raises(ReleaseError, match="Local release commit failed"):
        manager.release()

    assert (tmp_path / "pyproject.toml").read_text(encoding="utf-8") == original
    assert ["git", "restore", "--staged", "--", "pyproject.toml"] in runner.calls
    assert not any(call[1:3] == ["-m", "twine"] for call in runner.calls)


def test_upload_failure_keeps_release_commit_but_does_not_push_or_tag(tmp_path):
    make_project(tmp_path)
    runner = FakeRunner(project_dir=tmp_path, fail_command="twine")
    manager = ReleaseManager(
        "1.2.4",
        tmp_path,
        ProcessRunner(runner),
        lambda _: pytest.fail("unexpected prompt"),
    )

    with pytest.raises(ReleaseError, match="twine upload") as exc_info:
        manager.release()

    assert "simulated failure" in str(exc_info.value)
    assert ["git", "commit", "-m", "Release v1.2.4"] in runner.calls
    assert ["git", "reset", "--hard", "parent"] in runner.calls
    assert 'version = "1.2.3"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert not any(call[:2] == ["git", "push"] for call in runner.calls)
    assert not any(call[:2] == ["git", "tag"] for call in runner.calls)


def test_upload_failure_does_not_rollback_unrelated_newer_commit(tmp_path):
    make_project(tmp_path)
    runner = FakeRunner(project_dir=tmp_path, fail_command="twine")
    runner.head_changes = True
    manager = ReleaseManager(
        "1.2.4",
        tmp_path,
        ProcessRunner(runner),
        lambda _: pytest.fail("unexpected prompt"),
    )

    with pytest.raises(ReleaseError, match="HEAD changed"):
        manager.release()

    assert not any(call[:3] == ["git", "reset", "--hard"] for call in runner.calls)


def test_dirty_working_tree_stops_release_before_version_update(tmp_path):
    make_project(tmp_path)
    original = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    runner = FakeRunner(project_dir=tmp_path, dirty=True)
    manager = ReleaseManager(
        "1.2.4",
        tmp_path,
        ProcessRunner(runner),
        lambda _: pytest.fail("unexpected prompt"),
    )

    with pytest.raises(ReleaseError, match="Working tree is not clean"):
        manager.release()

    assert (tmp_path / "pyproject.toml").read_text(encoding="utf-8") == original
    assert not any(call[1:3] == ["-m", "build"] for call in runner.calls)
