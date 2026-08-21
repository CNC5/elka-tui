"""Tree element: a hierarchy of labelled nodes with branch glyphs."""

from dataclasses import dataclass, field
from typing import List

from .base import Element, resolve


@dataclass
class TreeNode:
    """A node in the tree. ``expanded`` controls whether children are shown."""

    label: str
    children: List["TreeNode"] = field(default_factory=list)
    expanded: bool = True


class Tree(Element):
    """Render a tree (or forest) depth-first with box-drawing branch glyphs.

    :param provider: ``() -> TreeNode | list[TreeNode]`` (the element's input
        class is ``TreeNode``; a list is treated as a forest of roots),
        re-invoked every frame. A constant value is also accepted.

    Roots print flush-left; descendants get ``├─``/``└─`` branch glyphs with
    ``│``/space guides for their ancestors, e.g.::

        root
        ├─ src
        │  └─ main.py
        └─ README
    """

    def __init__(self, provider):
        self.provider = provider

    def _roots(self):
        roots = resolve(self.provider)
        return [roots] if isinstance(roots, TreeNode) else roots

    def content_height(self, width):
        return sum(1 for _ in self._lines(self._roots(), prefix="", is_root=True))

    def render(self, buf, rect):
        if rect.height <= 0 or rect.width <= 0:
            return

        roots = self._roots()

        row = rect.y
        bottom = rect.y + rect.height
        for line in self._lines(roots, prefix="", is_root=True):
            if row >= bottom:
                break
            buf.text(rect.x, row, line, max_width=rect.width)
            row += 1

    def _lines(self, nodes, prefix, is_root):
        """Yield rendered text lines for ``nodes``.

        ``prefix`` is the ancestor guide string; ``is_root`` suppresses branch
        glyphs for the outermost level.
        """
        last = len(nodes) - 1
        for i, node in enumerate(nodes):
            is_last = i == last
            if is_root:
                yield node.label
                child_prefix = prefix
            else:
                yield prefix + ("└─ " if is_last else "├─ ") + node.label
                child_prefix = prefix + ("   " if is_last else "│  ")
            if node.children and node.expanded:
                yield from self._lines(node.children, child_prefix, is_root=False)
