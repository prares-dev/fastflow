try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9 and 3.10
    import tomli as tomllib

from fastflow.commands.project import Configuration, ProjectManager


def test_generated_pyproject_is_valid_toml_and_includes_expected_metadata(tmp_path):
    config = Configuration(
        create_venv=False,
        create_gitignore=False,
        create_pyproject_toml=True,
        create_readme=True,
        create_license=False,
    )
    ProjectManager("My Example", config, tmp_path).create()

    content = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    metadata = tomllib.loads(content)

    assert metadata["build-system"] == {
        "requires": ["setuptools>=68"],
        "build-backend": "setuptools.build_meta",
    }
    assert metadata["project"]["name"] == "My-Example"
    assert metadata["project"]["version"] == "0.1.0"
    assert metadata["project"]["readme"] == "README.md"


def test_generated_metadata_omits_readme_when_not_created(tmp_path):
    config = Configuration(
        create_venv=False,
        create_gitignore=False,
        create_pyproject_toml=True,
        create_readme=False,
        create_license=False,
    )
    ProjectManager("Project One", config, tmp_path).create()

    metadata = tomllib.loads((tmp_path / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["name"] == "Project-One"
    assert "readme" not in metadata["project"]
