"""Scroll: a movable vertical window into a taller child element.

Elements clip to their rect and truncate anything past the bottom. Wrapping a
child in :class:`Scroll` instead renders it into an off-screen buffer as tall
as its content, then copies just the visible slice into the real region -- so
the extra rows become reachable by scrolling::

    terminal.attach(Scroll(Tree(big_tree)))
    terminal.on("down", lambda k: scroller.scroll_by(1))

The wrapper owns an integer row offset and clamps it to the child's content on
every frame, so callers never have to know how tall the content is.
"""

from .base import Element
from ..buffer import Buffer, Rect


class Scroll(Element):
    """Show a vertical window into ``child``, scrollable by row.

    :param child: the element to render and scroll.
    :param offset: initial scroll position, in rows from the top.

    The offset is clamped to ``[0, content_height - view_height]`` each frame
    (using the child's :meth:`~elka.elements.base.Element.content_height`), so
    it can never scroll past the last row or above the first. When the child
    reports no height, the visible height plus the current offset is rendered,
    which still scrolls but cannot clamp to a true bottom.
    """

    def __init__(self, child, offset=0):
        self.child = child
        self._offset = max(0, offset)
        self._scratch = Buffer()
        self._view_height = 0     # last render's visible rows (for paging)
        self._max_offset = 0      # last render's clamp ceiling

    # -- scrolling -----------------------------------------------------------
    @property
    def offset(self):
        """Current scroll position, in rows from the top."""
        return self._offset

    def scroll_by(self, delta):
        """Move the window ``delta`` rows (negative scrolls up). Clamped."""
        self.scroll_to(self._offset + delta)

    def scroll_to(self, row):
        """Move the window so ``row`` is the top visible row. Clamped."""
        self._offset = max(0, min(row, self._max_offset))

    def page_down(self, n=1):
        """Scroll down by ``n`` visible pages."""
        self.scroll_by(n * max(1, self._view_height))

    def page_up(self, n=1):
        """Scroll up by ``n`` visible pages."""
        self.scroll_by(-n * max(1, self._view_height))

    def to_top(self):
        """Scroll to the first row."""
        self.scroll_to(0)

    def to_bottom(self):
        """Scroll to the last row (as of the most recent frame)."""
        self.scroll_to(self._max_offset)

    # -- rendering -----------------------------------------------------------
    def render(self, buf, rect):
        if rect.height <= 0 or rect.width <= 0:
            return

        self._view_height = rect.height

        content_h = self.child.content_height(rect.width)
        if content_h is None:
            # Unknown height: render just enough to fill the current window.
            content_h = self._offset + rect.height
        content_h = max(content_h, rect.height)

        self._max_offset = max(0, content_h - rect.height)
        offset = self._offset = max(0, min(self._offset, self._max_offset))

        # Render the child in full into an off-screen buffer, then blit the
        # [offset : offset + height] slice into our region.
        self._scratch.resize(rect.width, content_h)
        self._scratch.clear()
        self.child.render(self._scratch, Rect(0, 0, rect.width, content_h))

        for row in range(rect.height):
            sy = offset + row
            if sy >= content_h:
                break
            for x in range(rect.width):
                cell = self._scratch.get(x, sy)
                buf.set(rect.x + x, rect.y + row, cell.char, cell.style)

    def content_height(self, width):
        """Defer to the child, so nesting scrollers behaves sensibly."""
        return self.child.content_height(width)
