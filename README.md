# flashflow

A small collection of Python commands for everyday development tasks.

## Install for development

```powershell
python -m pip install -e ".[dev]"
```

## Create a project scaffold

Run this from the directory where you want the initial project files:

```powershell
flashflow project "My Project"
```

The command creates a virtual environment, `.gitignore`, `README.md`, `LICENSE`,
and a valid `pyproject.toml` in the current directory. It refuses to overwrite
any of those files if they already exist. Choose an actual license before
distributing a generated project.

## Release a Python project

Run the command from the project root after choosing a new `X.Y.Z` version:

```powershell
flashflow release 1.2.3
```

The release command requires valid static `[project].version` metadata and a
clean Git working tree. It updates the version, builds distributions from an
isolated copy of the project, commits the version change locally, and uploads
only those fresh artifacts to PyPI. After a successful upload, it asks whether
to push the commit and whether to create and push a version tag.

If the build fails, the previous version is restored. If the PyPI upload fails,
the command attempts to remove its own release commit and restore the preceding
commit, but reports that PyPI may have accepted the upload before the failure
was returned. Verify the package on PyPI before retrying in that situation.