import subprocess
import sys


def run(commands: str, check: bool = True, capture: bool = True) -> str:
    """Run a shell command and return stdout."""
    result = subprocess.run(commands, check=check, capture_output=capture, text=True)
    if check and result.returncode != 0:
        print(f"❌ Error: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip()