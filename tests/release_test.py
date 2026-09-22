import pytest

from toolbox.commands.release import (
    _valid_version_format,
    _compare_version_increase_logic,
    _extract_current_version,
)

# ============== HELPER FUNCTIONS ============== #

@pytest.mark.parametrize("version", [
    ("1.0.2"), ("1.0.1"), ("2.43.53"),
])
def test_valid_version_format_with_nice_formmat(version):
    assert _valid_version_format(version) is None

@pytest.mark.parametrize("version", [
    ("1.y.9"), ("123.02"), ("2.2.3.4"), ("2,2,2"),
])
def test_valid_version_format_with_bad_formmat(version):
    with pytest.raises(ValueError):
        _valid_version_format(version)

@pytest.mark.parametrize("v, curr_v, expected", [
    ("1.1.2", "1.1.1", True),
    ("1.2.0", "1.1.6", True),
    ("2.5.2", "1.8.256", True),
    ("1.0.4", "1.1.2", False),
    ("0.3.4", "1.1.2", False),
    ("1.1.2", "1.1.2", False),
    ("1.1.1", "1.1.2", False),
])
def test_compare_version_increase_logic(v, curr_v, expected):
    assert _compare_version_increase_logic(v, curr_v) is expected

def test_extract_current_version_correctly_extracts_version(tmp_path):
    pyproject_path = tmp_path / "pyproject.toml"
    
    with pyproject_path.open('w', encoding='utf-8') as f:
        f.write('[project]\nauthor = "Pedro",\nversion = "1.2.3",')

    assert _extract_current_version(pyproject_path) == "1.2.3"

def test_extract_current_version_correctly_raises_exc(tmp_path):
    pyproject_path = tmp_path / "pyproject.toml"
    
    with pyproject_path.open('w', encoding='utf-8') as f:
        f.write('[project]\nauthor = "Pedro",')
    
    with pytest.raises(RuntimeError):
        _extract_current_version(pyproject_path)