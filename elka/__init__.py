"""elka — a small, stdlib-only TUI package.

A singleton :class:`Terminal` owns the screen. Elements are attached to it and
repainted on demand (``terminal.render()``). Data-driven elements take a
provider function that is re-invoked every frame, so callers update the UI just
by mutating whatever those functions read.
"""

from . import ansi, keys
from .buffer import Buffer, Cell, Rect
from .elements import (
    Element,
    HorizontalSplit,
    Scroll,
    Task,
    TaskList,
    Text,
    Tree,
    TreeNode,
)
from .terminal import Terminal, terminal

__all__ = [
    "Terminal",
    "terminal",
    "ansi",
    "keys",
    "Element",
    "HorizontalSplit",
    "Scroll",
    "TaskList",
    "Task",
    "Text",
    "Tree",
    "TreeNode",
    "Buffer",
    "Cell",
    "Rect",
]
