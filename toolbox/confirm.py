def confirm(prompt: str) -> bool:
    """Ask for yes/no confirmation."""
    response = input(f"{prompt} (y/n): ").strip().lower()
    return response in ("y", "yes")