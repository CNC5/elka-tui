"""Task list element: item names with optional progress bars."""

from dataclasses import dataclass
from typing import Optional

from .base import Element, resolve


@dataclass
class Task:
    """One task row. ``current``/``total`` are optional; when both are set a
    progress bar is drawn."""

    name: str
    current: Optional[int] = None
    total: Optional[int] = None

    @property
    def has_progress(self):
        return self.current is not None and self.total is not None


class TaskList(Element):
    """Render a list of :class:`Task` items, one per row.

    :param provider: ``() -> list[Task]`` (the element's input class is
        ``list[Task]``), re-invoked every frame. A constant list is also accepted.
    :param title: optional heading drawn on the first row.
    :param bar_width: width in cells of the progress bar.
    """

    def __init__(self, provider, title=None, bar_width=20):
        self.provider = provider
        self.title = title
        self.bar_width = bar_width

    def content_height(self, width):
        return (1 if self.title is not None else 0) + len(resolve(self.provider))

    def render(self, buf, rect):
        if rect.height <= 0 or rect.width <= 0:
            return

        row = rect.y
        bottom = rect.y + rect.height

        if self.title is not None and row < bottom:
            buf.text(rect.x, row, self.title, max_width=rect.width)
            row += 1

        for task in resolve(self.provider):
            if row >= bottom:
                break
            buf.text(rect.x, row, self._format(task, rect.width), max_width=rect.width)
            row += 1

    def _format(self, task, width):
        if not task.has_progress:
            return task.name

        total = task.total or 0
        frac = 0.0 if total <= 0 else max(0.0, min(1.0, task.current / total))
        filled = round(self.bar_width * frac)
        bar = "#" * filled + "-" * (self.bar_width - filled)
        return f"{task.name}  [{bar}] {task.current}/{task.total}"
