from argparse import Namespace
from dataclasses import dataclass

from ..process import run


@dataclass
class Configuration:
    create_venv: bool
    create_gitignore: bool
    create_pyproject_toml: bool
    create_readme: bool
    create_license: bool

class ProjectCreator:
    """Class for encapsulate all logic behind creating a new project structure."""
    def __init__(self, config: Configuration, project_name: str = "New Project"):
        """Inititalize atts."""
        self.name = project_name
        self.config = config
        self.internal_log = []
    
    def start(self):
        """ Core handler for all pieces of project structure. """
        try:
            self._create_venv()
            self._create_gitignore()
            self._create_readme()
            self._create_license()
            self._create_pyproject_toml()
        except Exception:
            for line in self.internal_log:
                print(line)
    
    def _create_venv(self):
        """Create a venv for the project using standar python module 'venv'."""
        if not self.config.create_venv:
            self.internal_log.append("⏭️ Skipped venv creation.")
            return
        
        command = f"py -m venv .venv --prompt '{self.name}-dev-venv'"
        try:
            run(command)
        except Exception:
            self.internal_log.append(f"❌ Something went wrong while running ({command}).")
            raise
        else:
            self.internal_log.append("✅ venv succesfully created")
    
    def _create_gitignore(self):
        """Create a gitignore file for the project with some initial useful ignores."""
        if not self.config.create_gitignore:
            self.internal_log.append("⏭️ Skipped .gitignore creation.")
            return
        
        try:
            path = ".gitignore"
            ignore = ["__pycache__/\n", ".venv\n", ".vscode\n"]
            with open(path, 'x', encoding='utf-8') as f:
                f.writelines(ignore)
        except Exception:
            self.internal_log.append("❌ Something went wrong while creating .gitignore file")
            raise
        else:
            self.internal_log.append("✅ .gitignore succesfully created")
    
    def _create_readme(self):
        """Create a readme file for the project."""
        if not self.config.create_readme:
            self.internal_log.append("⏭️ Skipped README.md creation.")
            return

        try:
            path = "README.md"
            with open(path, 'x', encoding='utf-8') as f:
                f.write(f"# `{self.name}` readme file.")
        except Exception:
            self.internal_log.append("❌ Something went wrong while creating README.md file")
            raise
        else:
            self.internal_log.append("✅ README.md succesfully created")
    
    def _create_license(self):
            """Create a readme file for the project."""
            if not self.config.create_license:
                self.internal_log.append("⏭️ Skipped LICENSE creation.")
                return
    
            try:
                path = "LICENSE"
                with open(path, 'x', encoding='utf-8') as f:
                    f.write("License file (fill in)")
            except Exception:
                self.internal_log.append("❌ Something went wrong while creating LICENSE file")
                raise
            else:
                self.internal_log.append("✅ LICENSE succesfully created")
    
    def _create_pyproject_toml(self):
        """Create a pyproject.toml file for the project with initial structure."""
        if not self.config.create_pyproject_toml:
            self.internal_log.append("⏭️ Skipped pyproject.toml creation.")
            return
        
        try:
            path = "pyproject.toml"
            lines = [
                "[build-system]\n", "requires = '___'\n", "build-backend = '___'\n", "\n"
                "[project]\n", f"name = {self.name}\n", "version = 0.1.0", "description = '___'",
                "readme = README.md" if self.config.create_readme  else "" ,
                "license = {file = LICENSE}" if self.config.create_license  else "" ,
                "requires-python = '___'", "authors = '[{name = \"___\", email = \"___\"}]'\n", 
                "dependencies = []"
            ]
            with open(path, 'x', encoding='utf-8') as f:
                f.writelines(lines)
        except Exception:
            self.internal_log.append("❌ Something went wrong while creating pyproject.toml file")
            raise
        else:
            self.internal_log.append("✅ pyproject.toml succesfully created")


def main(args: Namespace) -> None:
    name = args.name
    
    config = Configuration(
        create_venv=True,
        create_gitignore=True,
        create_pyproject_toml=True,
        create_readme=True,
        create_license=True,
    )
    
    pc = ProjectCreator(config, name)