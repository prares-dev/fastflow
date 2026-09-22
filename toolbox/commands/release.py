import re
import shutil
import sys
from argparse import Namespace
from pathlib import Path

from ..confirm import confirm
from ..process import run

VERSION_RE = re.compile(r'^version\s*=\s*"(\d+\.\d+\.\d+)",?$', flags=re.MULTILINE)

def _valid_version_format(version: str):
    """Raises ValueError if the version passed doesn't have the correct format."""
    if re.fullmatch(r"\d+\.\d+\.\d+", version) is None:
        raise ValueError()

def _extract_current_version(pyproject_path: Path) -> str:
    """Searches through the given path for the actual version of the project and returns it. 
    If don't found then raise RuntimeError"""

    content = pyproject_path.read_text()
    current_version_matches = re.findall(VERSION_RE, content)
    
    if current_version_matches:
        return current_version_matches[0]
    else: 
        raise RuntimeError()

def _compare_version_increase_logic(new, current) -> bool:
    """ Validates correct version increase. """
    for v in [new, current]: 
        _valid_version_format(v)
    n_major, n_minor, n_patch = new.split('.')
    c_major, c_minor, c_patch = current.split('.')
    
    if n_major > c_major:
        return True
    elif n_major < c_major: 
        return False
    
    if n_minor > c_minor:
        return True
    elif n_minor < c_minor:
        return False
    
    if n_patch > c_patch:
        return True
    elif n_patch <= c_patch:
        return False

    raise RuntimeError("Shouldn't reach here")

# NOT TESTED
def _check_git_branch() -> bool:
    """Check there's a git repository and we're in the main branch"""
    branch = None
    try:
        branch = run("git rev-parse --abbrev-ref HEAD", check=True)
    except Exception: # not a git repository
        print("⚠️  No git repository in the actual directory.")
        if not confirm("Continue anyway?"):
            return False
    
    if branch != "main":
        print(f"⚠️  You are on branch '{branch}', not 'main'.")
        if not confirm("Continue anyway?"):
            return False
    
    # Check working directory is clean
    status = run("git status --porcelain", check=False)
    if status:
        print("❌ You have uncommited changes, commit or stash them")
        print(status)
        return False
    
    return True

# NOT TESTED
def _update_version(pyproject_path: Path, version: str):
    """ Handles update of new version in the pyproject.toml file. """
    content = pyproject_path.read_text()
    new_content = re.sub(VERSION_RE, f'version = "{version}"', content)
    
    if new_content == content:
        raise RuntimeError()
    
    with open(pyproject_path, "w", encoding="utf-8") as f:
        f.write(new_content)

# NOT TESTED
def _commit(pyproject_path: Path, version: str, push: bool) -> None:
    # Commit the change
    run(f"git add {pyproject_path}")
    commit_msg = f"Release v{version}"
    run(f'git commit -m "{commit_msg}"')
    print(f"✅ Committed with message: {commit_msg}")
    
    if push:
        run("git push")
        print("✅ Pushed commit.")

def main(args: Namespace) -> None:
    
    # Check for correct version format
    version = args.version.strip()
    try:
        _valid_version_format(version)
    except ValueError:
        print("❌ Version must follow semantic versioning: X.Y.Z")
        return
    
    # Search for a pyproject.toml file
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        # ask for creating default pyproject.toml before continue
        raise FileNotFoundError("❌ pyproject.toml not found.")
    
    # Extract current version from pyproject.toml
    try:
        current_version = _extract_current_version(pyproject_path)
    except RuntimeError:
        print(f"❌ version not found in {pyproject_path}")
        return

    # Compare new and current versions for logic versioning
    if not _compare_version_increase_logic(version, current_version):
        print(f"❌ Invalid version bump from {current_version} to {version}.")
        return

    # Check git repository and branch correct status
    if not _check_git_branch():
        return
    
    # Update version in pyproject.toml
    try: 
        _update_version(pyproject_path, version)
        print(f"✅ Updated version to {version} in pyproject.toml")
    except RuntimeError:
        print("❌ Couldn't update version. Check pyproject.toml file.")

    # Commit and optionally push commit
    push = confirm("Push the commit to origin?")
    _commit(pyproject_path, version, push)

    # Optional: create and push tag
    if confirm(f"Create and push git tag v{version}?"):
        run(f"git tag v{version}")
        run(f"git push origin v{version}")
        print("✅ Tag pushed.")

    # Build the package
    print("📦 Building package...")
    try:
        run("python -m build")
    except Exception as exc:
        print(f"❌ Build failed: {exc}")
        return
    print("✅ Build completed.")

    # Upload to PyPI
    print("⬆️  Uploading to PyPI...")
    try:
        run("python -m twine upload dist/*")
    except Exception as exc:
        print(f"❌ Upload failed. {exc}")
        return
    print("✅ Upload completed.")

    print("\n🎉 Release v{version} successful!")
    
    # Delete residuals
    for dir_name in ["dist", "easydone.egg-info"]:
        dir_path = Path(dir_name)
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"🗑️  Removed {dir_path}")