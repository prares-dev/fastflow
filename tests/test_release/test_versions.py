import pytest

from fastflow.commands.release import ReleaseError, ReleaseManager


@pytest.mark.parametrize("version", ["0.0.0", "1.0.2", "2.43.53"])
def test_validate_version_accepts_x_y_z(version):
    assert ReleaseManager.validate_version(version) is not None


@pytest.mark.parametrize(
    "version",
    ["", "1.y.9", "123.02.1", "2.2.3.4", "2,2,2", "1.0.0rc1"],
)
def test_validate_version_rejects_invalid_versions(version):
    with pytest.raises(ReleaseError, match="X.Y.Z"):
        ReleaseManager.validate_version(version)


@pytest.mark.parametrize(
    ("new", "current", "expected"),
    [
        ("1.1.2", "1.1.1", True),
        ("1.2.0", "1.1.6", True),
        ("2.5.2", "1.8.256", True),
        ("10.0.0", "2.99.99", True),
        ("1.0.4", "1.1.2", False),
        ("0.3.4", "1.1.2", False),
        ("1.1.2", "1.1.2", False),
        ("1.1.1", "1.1.2", False),
    ],
)
def test_is_version_increase_compares_numeric_components(new, current, expected):
    assert ReleaseManager.is_version_increase(new, current) is expected


def test_read_current_version_reads_project_metadata(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "1.2.3"\n',
        encoding="utf-8",
    )

    assert ReleaseManager("1.2.4", tmp_path).read_current_version() == "1.2.3"


@pytest.mark.parametrize(
    "content",
    [
        "[tool.demo]\nversion = '1.2.3'\n",
        '[project]\nname = "demo"\n',
        '[project]\nname = "demo"\ndynamic = ["version"]\n',
        '[project]\nname = "demo"\nversion = "1.02.3"\n',
        '[project]\nname = "demo"\nversion = "1.2.3"\nversion = "1.2.4"\n',
    ],
)
def test_read_current_version_rejects_missing_dynamic_or_invalid_versions(tmp_path, content):
    (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")

    with pytest.raises(ReleaseError):
        ReleaseManager("1.2.4", tmp_path).read_current_version()


def test_read_current_version_rejects_malformed_toml(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project\n", encoding="utf-8")

    with pytest.raises(ReleaseError, match="Invalid TOML"):
        ReleaseManager("1.2.4", tmp_path).read_current_version()
