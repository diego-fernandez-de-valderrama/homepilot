from rich.console import Console

# All CLI output goes to stderr (stdout stays free for data), through this one console.
CONSOLE = Console(stderr=True)
