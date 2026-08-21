"""Off-screen cell grid used for flicker-free rendering.

Elements draw into a :class:`Buffer` (a grid of :class:`Cell`). The terminal
then diffs the freshly drawn buffer against the previously displayed one and
emits ANSI only for the cells that actually changed.
"""

from dataclasses import dataclass, field


@dataclass
class Rect:
    """A rectangular region, in 0-indexed terminal coordinates."""

    x: int
    y: int
    width: int
    height: int

    def split_horizontal(self, top_height):
        """Split into ``(top, bottom)`` by a horizontal divider line.

        ``top_height`` rows go to the top; the remainder go to the bottom.
        The value is clamped to ``[0, height]``.
        """
        top_h = max(0, min(self.height, top_height))
        top = Rect(self.x, self.y, self.width, top_h)
        bottom = Rect(self.x, self.y + top_h, self.width, self.height - top_h)
        return top, bottom


@dataclass
class Cell:
    """A single screen cell: one character plus an optional SGR style prefix."""

    char: str = " "
    style: str = ""

    def __eq__(self, other):
        return (
            isinstance(other, Cell)
            and self.char == other.char
            and self.style == other.style
        )


class Buffer:
    """A ``width x height`` grid of :class:`Cell`."""

    def __init__(self, width=0, height=0):
        self.width = width
        self.height = height
        self._grid = self._blank(width, height)

    @staticmethod
    def _blank(width, height):
        return [[Cell() for _ in range(width)] for _ in range(height)]

    def resize(self, width, height):
        """Resize the grid, discarding contents. No-op if unchanged."""
        if width == self.width and height == self.height:
            return
        self.width = width
        self.height = height
        self._grid = self._blank(width, height)

    def clear(self):
        """Reset every cell to a blank space with default style."""
        for row in self._grid:
            for cell in row:
                cell.char = " "
                cell.style = ""

    def get(self, x, y):
        return self._grid[y][x]

    def set(self, x, y, char, style=""):
        """Set a single cell, ignoring out-of-bounds writes."""
        if 0 <= y < self.height and 0 <= x < self.width:
            cell = self._grid[y][x]
            cell.char = char
            cell.style = style

    def text(self, x, y, s, style="", max_width=None):
        """Draw ``s`` starting at ``(x, y)``, clipped to the buffer / max_width."""
        if max_width is not None:
            s = s[:max_width]
        for i, ch in enumerate(s):
            self.set(x + i, y, ch, style)

    def hline(self, x, y, width, char="-", style=""):
        """Draw a horizontal line of ``char``."""
        for i in range(width):
            self.set(x + i, y, char, style)

    def diff(self, prev):
        """Cells that differ from ``prev`` as ``(x, y, Cell)`` tuples.

        If ``prev`` has different dimensions (e.g. after a resize), every cell
        is reported so the terminal repaints in full.
        """
        changes = []
        full = prev is None or prev.width != self.width or prev.height != self.height
        for y in range(self.height):
            for x in range(self.width):
                cell = self._grid[y][x]
                if full or cell != prev._grid[y][x]:
                    changes.append((x, y, cell))
        return changes
