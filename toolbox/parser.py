"""
Module to centralize all handling of arguments throug CLI
"""


from argparse import ArgumentParser, Namespace

from .commands import project, release


class Parser:
    """A class to manage all the argument parser and command features."""

    def __init__(self) -> None:
        """Initialize the CLIApp attributes."""
        self.main_parser = self.build_parser()

    def build_parser(self) -> ArgumentParser:
        """Create the main parser and sub-commands."""
        parser = ArgumentParser(
            prog="toolbox", 
            description="\"toolbox\" is a set of programs written in python \
                to make easier everyday workflow",
            allow_abbrev=False, 
            epilog="Thanks for using %(prog)s, all feedback is appreciated"
        ) 
        
        sub_commands = parser.add_subparsers(title="Programs", help="Programs available")
        
        # PROJECT
        new_project_parser = sub_commands.add_parser(
            "project",
            help = "Create the initial structure for a new project in the current directory"
        )
        
        new_project_parser.add_argument(
            "name", type=str, help="Name of the project to be created."
        )
        
        new_project_parser.set_defaults(func=project.main)
        
        # RELEASE
        release_parser = sub_commands.add_parser(
            "release", 
            help = "Release an especific version of a program/package to PyPi."
        )
        
        release_parser.add_argument(
            "version", type=str, help="Version of the program to be uploaded"
        )
        release_parser.set_defaults(func=release.main)
        
        return parser

    def start_parsing(self) -> None:
        """Parses the arguments passed."""
        args: Namespace
        try:
            args = self.main_parser.parse_args()
        except ValueError as exc:
            self.main_parser.error(str(exc))

        if not hasattr(args, "func"):
            # in case user invokes the program without arguments like:
            # >>> toolbox
            self.main_parser.print_help()
            return
        
        try:
            return args.func(args)
        except (KeyError, ValueError) as exc:
            self.main_parser.error(str(exc))