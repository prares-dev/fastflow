"""Create a safe, usable initial structure for a Python project."""

from __future__ import annotations

import json
import re
import shutil
import sys
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path

from ..process import CommandExecutionError, ProcessRunner


@dataclass(frozen=True)
class Configuration:
    """Select which project files and environment should be created."""

    create_venv: bool = True
    create_gitignore: bool = True
    create_pyproject_toml: bool = True
    create_readme: bool = True
    create_license: bool = True


class ProjectError(RuntimeError):
    """An expected failure while creating a project scaffold."""


class ProjectManager:
    """Create project files without overwriting existing user data."""

    def __init__(
        self,
        project_name: str,
        config: Configuration | None = None,
        project_dir: Path | str | None = None,
        runner: ProcessRunner | None = None,
    ) -> None:
        self.name = project_name.strip()
        if not self.name or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ -]*", self.name) is None:
            raise ProjectError(
                "Project name must start with a letter or digit and contain only "
                "letters, digits, spaces, '.', '_' or '-'."
            )

        self.distribution_name = re.sub(r"[-_. ]+", "-", self.name).strip("-")
        if not self.distribution_name:
            raise ProjectError("Project name must contain at least one letter or digit.")

        self.config = config or Configuration()
        self.project_dir = Path.cwd() if project_dir is None else Path(project_dir).resolve()
        self.runner = runner or ProcessRunner()
        self._created_paths: list[Path] = []

    def _file_contents(self) -> dict[str, str]:
        files: dict[str, str] = {}

        if self.config.create_gitignore:
            files[".gitignore"] = (
                "__pycache__/\n"
                "*.py[cod]\n"
                ".venv/\n"
                ".vscode/\n"
                ".cache/\n"
                "build/\n"
                "dist/\n"
                "*.egg-info/\n"
            )
        if self.config.create_readme:
            files["README.md"] = f"# {self.name}\n\nA short description of this project.\n"
        if self.config.create_license:
            files["LICENSE"] = "Choose and add a license before distributing this project.\n"
        if self.config.create_pyproject_toml:
            files["pyproject.toml"] = self._pyproject_contents()

        return files

    def _pyproject_contents(self) -> str:
        lines = [
            "[build-system]",
            'requires = ["setuptools>=68"]',
            'build-backend = "setuptools.build_meta"',
            "",
            "[project]",
            f"name = {json.dumps(self.distribution_name)}",
            'version = "0.1.0"',
            f"description = {json.dumps('A Python project named ' + self.name + '.')}",
            'requires-python = ">=3.9"',
            "dependencies = []",
        ]
        if self.config.create_readme:
            lines.append('readme = "README.md"')
        lines.append("")
        return "\n".join(lines)

    def _preflight(self, files: dict[str, str]) -> None:
        if not self.project_dir.is_dir():
            raise ProjectError(f"Project directory does not exist: {self.project_dir}")

        requested_paths = [self.project_dir / filename for filename in files]
        if self.config.create_venv:
            requested_paths.append(self.project_dir / ".venv")

        conflicts = [
            path.name for path in requested_paths if path.exists() or path.is_symlink()
        ]
        if conflicts:
            joined = ", ".join(conflicts)
            raise ProjectError(
                f"Refusing to overwrite existing project content in {self.project_dir}: "
                f"{joined}"
            )

    def create(self) -> list[Path]:
        """Create the selected scaffold, rolling back only files created by this run."""
        files = self._file_contents()
        self._preflight(files)
        self._created_paths = []

        try:
            for filename, content in files.items():
                path = self.project_dir / filename
                with path.open("x", encoding="utf-8", newline="\n") as project_file:
                    self._created_paths.append(path)
                    project_file.write(content)

            if self.config.create_venv:
                self._create_venv()
        except (OSError, CommandExecutionError, ProjectError) as exc:
            rollback_errors = self._rollback()
            message = f"Project creation failed: {exc}"
            if rollback_errors:
                message += "\nCleanup was incomplete:\n" + "\n".join(rollback_errors)
            raise ProjectError(message) from exc

        return list(self._created_paths)

    def _create_venv(self) -> None:
        venv_path = self.project_dir / ".venv"
        venv_path.mkdir()
        self._created_paths.append(venv_path)
        prompt = f"{self.distribution_name}-dev-venv"
        self.runner.run(
            [sys.executable, "-m", "venv", str(venv_path), "--prompt", prompt],
            cwd=self.project_dir,
        )

    def _rollback(self) -> list[str]:
        rollback_errors: list[str] = []
        for path in reversed(self._created_paths):
            try:
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
            except OSError as exc:
                rollback_errors.append(f"{path}: {exc}")
        self._created_paths.clear()
        return rollback_errors


def main(args: Namespace) -> None:
    """Entry point for the project command."""
    try:
        created = ProjectManager(args.name).create()
    except ProjectError as exc:
        print(f"Project creation failed: {exc}")
        raise SystemExit(1) from exc

    for path in created:
        print(f"Created {path.name}.")
