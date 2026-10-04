"""Build and publish a new release of the current Python project."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from argparse import Namespace
from collections.abc import Sequence
from pathlib import Path
from typing import Callable

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9 and 3.10
    import tomli as tomllib  # type: ignore

from ..confirm import confirm
from ..process import CommandExecutionError, ProcessRunner

_VERSION_RE = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")
_SECTION_RE = re.compile(r"^\s*\[([^\]]+)]\s*(?:#.*)?$")
_VERSION_LINE_RE = re.compile(
    r"""(?P<prefix>\s*version\s*=\s*)(?P<quote>["'])(?P<version>[^"']+)(?P=quote)"""
    r"""(?P<suffix>\s*(?:\#.*)?)(?P<newline>\r?\n?)\Z"""
)
Confirmer = Callable[[str], bool]


class ReleaseError(RuntimeError):
    """An expected failure while preparing or publishing a release."""


class ReleaseManager:
    """Coordinate release validation, local build/commit, and optional publication."""

    def __init__(
        self,
        version: str,
        project_dir: Path | str | None = None,
        runner: ProcessRunner | None = None,
        confirmer: Confirmer = confirm,
    ) -> None:
        self.version = version.strip()
        self.project_dir = Path.cwd() if project_dir is None else Path(project_dir).resolve()
        self.pyproject_path = self.project_dir / "pyproject.toml"
        self._runner = runner or ProcessRunner()
        self._confirm = confirmer

    @staticmethod
    def validate_version(version: str) -> tuple[int, int, int]:
        """Validate and return a strict numeric X.Y.Z version."""
        match = _VERSION_RE.fullmatch(version)
        if match is None:
            raise ReleaseError("Version must follow semantic versioning: X.Y.Z.")
        return tuple(map(int, match.groups())) # type: ignore

    @classmethod
    def is_version_increase(cls, new_version: str, current_version: str) -> bool:
        """Return whether a valid version is greater than the current version."""
        return cls.validate_version(new_version) > cls.validate_version(current_version)

    def read_current_version(self) -> str:
        """Read the static project version from valid TOML project metadata."""
        if not self.pyproject_path.is_file():
            raise ReleaseError(f"{self.pyproject_path} not found.")

        content = self._read_pyproject_content()
        try:
            metadata = tomllib.loads(content)
        except tomllib.TOMLDecodeError as exc:
            raise ReleaseError(f"Invalid TOML in {self.pyproject_path}: {exc}") from exc

        project = metadata.get("project")
        if not isinstance(project, dict) or not isinstance(project.get("version"), str):
            raise ReleaseError(f"A static [project].version is required in {self.pyproject_path}.")

        version = project["version"]
        self.validate_version(version)
        return version

    def update_version(self, version: str) -> None:
        """Atomically replace only [project].version, preserving the rest of the file."""
        self.validate_version(version)
        content = self._read_pyproject_content()
        lines = content.splitlines(keepends=True)
        project_start = None
        project_end = len(lines)

        for index, line in enumerate(lines):
            section = _SECTION_RE.fullmatch(line.rstrip("\r\n"))
            if section is None:
                continue
            if section.group(1) == "project":
                project_start = index + 1
            elif project_start is not None:
                project_end = index
                break

        if project_start is None:
            raise ReleaseError(f"[project].version not found in {self.pyproject_path}.")

        for index in range(project_start, project_end):
            match = _VERSION_LINE_RE.fullmatch(lines[index])
            if match is not None:
                lines[index] = (
                    f"{match.group('prefix')}{match.group('quote')}{version}"
                    f"{match.group('quote')}{match.group('suffix')}{match.group('newline')}"
                )
                self._write_atomically("".join(lines))
                return

        raise ReleaseError(f"[project].version must be a static string in {self.pyproject_path}.")

    def _read_pyproject_content(self) -> str:
        try:
            return self.pyproject_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ReleaseError(f"Could not read {self.pyproject_path}: {exc}") from exc

    def _write_atomically(self, content: str) -> None:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=self.project_dir,
                prefix=".pyproject-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.chmod(temporary_path, self.pyproject_path.stat().st_mode)
            os.replace(temporary_path, self.pyproject_path)
        except OSError as exc:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    raise ReleaseError(
                        f"Could not update {self.pyproject_path}; failed to remove "
                        f"{temporary_path}: {cleanup_error}"
                    ) from cleanup_error
            raise ReleaseError(f"Could not update {self.pyproject_path}: {exc}") from exc

    def _run(
        self, command: Sequence[str], cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        try:
            return self._runner.run(command, cwd=cwd or self.project_dir)
        except CommandExecutionError as exc:
            raise ReleaseError(str(exc)) from exc

    def check_git_state(self) -> None:
        """Require a Git checkout with a clean working tree."""
        branch = self._run(["git", "branch", "--show-current"]).stdout.strip()
        if not branch:
            raise ReleaseError("Cannot release from a detached HEAD.")
        if branch != "main" and not self._confirm(
            f"You are on branch '{branch}', not 'main'. Continue anyway?"
        ):
            raise ReleaseError("Release cancelled.")

        status = self._run(["git", "status", "--porcelain"]).stdout.strip()
        if status:
            raise ReleaseError(
                f"Working tree is not clean; commit or stash changes first:\n{status}"
            )

    def build(self, output_dir: Path, source_dir: Path) -> list[Path]:
        """Build a copied source tree so backends leave no generated files in the project."""
        output_dir.mkdir(parents=True, exist_ok=True)
        self._run(
            [
                sys.executable,
                "-m",
                "build",
                "--outdir",
                str(output_dir),
            ],
            cwd=source_dir,
        )
        artifacts = sorted(path for path in output_dir.iterdir() if path.is_file())
        if not artifacts:
            raise ReleaseError("Build completed but produced no distribution files.")
        return artifacts

    def commit(self) -> tuple[str, str]:
        """Commit the version change locally and return its parent and new commit IDs."""
        parent = self._run(["git", "rev-parse", "HEAD"]).stdout.strip()
        # -- prevents ambiguity and ensures Git treats pyproject.toml as a path,
        # not as a git option.
        self._run(["git", "add", "--", "pyproject.toml"])
        self._run(["git", "commit", "-m", f"Release v{self.version}"])
        release_commit = self._run(["git", "rev-parse", "HEAD"]).stdout.strip()
        if not parent or not release_commit or parent == release_commit:
            raise ReleaseError("Could not verify the local release commit.")
        return parent, release_commit

    def upload(self, artifacts: Sequence[Path]) -> None:
        """Upload only artifacts produced by this release build."""
        self._run([sys.executable, "-m", "twine", "upload", *(str(path) for path in artifacts)])

    def publish_to_git(self) -> None:
        """Offer optional branch push and version-tag publication."""
        if self._confirm("Push the release commit to origin?"):
            try:
                self._run(["git", "push"])
            except ReleaseError as exc:
                raise ReleaseError(
                    f"PyPI upload succeeded, but pushing the release commit failed: {exc}"
                ) from exc
            print("Pushed release commit.")

        tag = f"v{self.version}"
        if self._confirm(f"Create and push git tag {tag}?"):
            try:
                self._run(["git", "tag", tag])
                self._run(["git", "push", "origin", tag])
            except ReleaseError as exc:
                raise ReleaseError(
                    f"PyPI upload succeeded, but publishing Git tag {tag} failed: {exc}"
                ) from exc
            print(f"Pushed tag {tag}.")

    def release(self) -> None:
        """Validate, build, commit, upload, and optionally publish to Git."""
        self.validate_version(self.version)
        current_version = self.read_current_version()
        if not self.is_version_increase(self.version, current_version):
            raise ReleaseError(
                f"Invalid version bump from {current_version} to {self.version}."
            )
        self.check_git_state()

        original_content = self._read_pyproject_content()
        self.update_version(self.version)
        print(f"Updated version to {self.version} in pyproject.toml.")

        with tempfile.TemporaryDirectory(prefix="fastflow-release-") as temporary_dir:
            build_root = Path(temporary_dir)
            output_dir = build_root / "dist"
            source_dir = build_root / "source"
            try:
                print("Building package...")
                shutil.copytree(
                    self.project_dir,
                    source_dir,
                    ignore=self._ignore_build_files,
                )
                artifacts = self.build(output_dir, source_dir)
            except (OSError, ReleaseError) as exc:
                self._write_atomically(original_content)
                raise ReleaseError(
                    f"Build failed; restored the original project version. {exc}"
                ) from exc
            print("Build completed.")

            try:
                parent_commit, release_commit = self.commit()
            except ReleaseError as exc:
                self._restore_after_commit_failure(original_content)
                raise ReleaseError(
                    f"Local release commit failed; restored the original project version. {exc}"
                ) from exc
            print(f"Committed release v{self.version}.")

            print("Uploading to PyPI...")
            try:
                self.upload(artifacts)
            except ReleaseError as exc:
                try:
                    self._rollback_release_commit(parent_commit, release_commit)
                except ReleaseError as rollback_error:
                    raise ReleaseError(
                        f"PyPI upload failed: {exc}\n"
                        f"Could not safely roll back the local release commit: {rollback_error}"
                    ) from exc
                raise ReleaseError(
                    "PyPI upload failed; the local release commit was removed and "
                    f"the previous version restored. PyPI may have accepted the upload "
                    f"before the failure was reported. {exc}"
                ) from exc
            print("Upload completed.")

        self.publish_to_git()
        print(f"Release v{self.version} successful.")

    @staticmethod
    def _ignore_build_files(directory: str, names: list[str]) -> set[str]:
        del directory
        ignored = {
            ".git",
            ".venv",
            ".cache",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
            "build",
            "dist",
        }
        return {
            name
            for name in names
            if name in ignored or name.endswith(".egg-info")
        }

    def _rollback_release_commit(self, parent_commit: str, release_commit: str) -> None:
        head = self._run(["git", "rev-parse", "HEAD"]).stdout.strip()
        if head != release_commit:
            raise ReleaseError(
                "HEAD changed after the release commit; refusing to reset unrelated history."
            )

        status = self._run(["git", "status", "--porcelain"]).stdout.strip()
        if status:
            raise ReleaseError(
                "The working tree changed after the release commit; refusing to discard "
                f"those changes:\n{status}"
            )

        self._run(["git", "reset", "--hard", parent_commit])

    def _restore_after_commit_failure(self, original_content: str) -> None:
        unstage_error = None
        try:
            self._run(["git", "restore", "--staged", "--", "pyproject.toml"])
        except ReleaseError as exc:
            unstage_error = exc
        self._write_atomically(original_content)
        if unstage_error is not None:
            raise ReleaseError(
                "Restored the project version but could not unstage pyproject.toml: "
                f"{unstage_error}"
            ) from unstage_error


def main(args: Namespace) -> None:
    """Entry point for the release command."""
    try:
        ReleaseManager(args.version).release()
    except ReleaseError as exc:
        print(f"Release failed: {exc}")
        raise SystemExit(1) from exc
