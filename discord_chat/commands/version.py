"""Version command - displays project version from pyproject.toml."""

from pathlib import Path

import click

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def get_version() -> str:
    """Read version from pyproject.toml."""
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"

    if not pyproject_path.exists():
        return "unknown"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    return data.get("project", {}).get("version", "unknown")


@click.command()
def version() -> None:
    """Display the current version."""
    click.echo(f"discord-chat version {get_version()}")
