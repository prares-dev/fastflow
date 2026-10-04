import pytest

from flashflow.commands.release import ReleaseError, ReleaseManager


def test_update_version_only_changes_project_version_and_preserves_comment(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    original = (
        '[project]\nname = "demo"\nversion  = \'1.2.3\' # current\n\n'
        "[tool.demo]\nversion = '9.8.7'\n"
    )
    pyproject.write_text(original, encoding="utf-8")

    ReleaseManager("1.2.4", tmp_path).update_version("1.2.4")

    assert pyproject.read_text(encoding="utf-8") == original.replace(
        "version  = '1.2.3' # current",
        "version  = '1.2.4' # current",
    )


@pytest.mark.parametrize(
    "content",
    [
        "[tool.demo]\nversion = '1.2.3'\n",
        '[project]\nname = "demo"\ndynamic = ["version"]\n',
    ],
)
def test_update_version_rejects_missing_static_project_version(tmp_path, content):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(content, encoding="utf-8")

    with pytest.raises(ReleaseError, match=r"\[project\]\.version"):
        ReleaseManager("1.2.4", tmp_path).update_version("1.2.4")


def test_update_version_rejects_invalid_requested_version(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")

    with pytest.raises(ReleaseError, match="X.Y.Z"):
        ReleaseManager("1.2.4", tmp_path).update_version("2.0")
