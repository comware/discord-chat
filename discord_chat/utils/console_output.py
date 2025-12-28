"""Console output utilities with Rich markdown rendering."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

# Re-export Console for type annotations
__all__ = ["Console", "create_console", "render_digest_to_console"]


def create_console(force_terminal: bool | None = None, no_color: bool = False) -> Console:
    """Create a Rich console instance.

    Args:
        force_terminal: Force terminal mode (for testing). None for auto-detect.
        no_color: If True, disable colors and styling.

    Returns:
        Configured Console instance.
    """
    return Console(
        force_terminal=force_terminal,
        no_color=no_color,
        highlight=not no_color,
    )


def render_digest_to_console(
    digest_content: str,
    console: Console | None = None,
    quiet: bool = False,
) -> None:
    """Render markdown digest to the terminal with Rich formatting.

    Args:
        digest_content: The markdown content to render.
        console: Optional Console instance (for testing). Creates new if None.
        quiet: If True, suppress all output.
    """
    if quiet:
        return

    if console is None:
        console = create_console()

    # Render markdown content in a styled panel
    md = Markdown(digest_content)
    panel = Panel(
        md,
        title="Discord Digest",
        border_style="blue",
        padding=(1, 2),
    )
    console.print(panel)
