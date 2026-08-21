"""Base class shared by all renderable elements."""

from abc import ABC, abstractmethod

from ..dispatch import KeyDispatch


class Element(KeyDispatch, ABC):
    """Something that can draw itself into a rectangular region of a buffer.

    Implementations must clip all drawing to ``rect``; nothing may write
    outside its assigned region.

    An element is also a :class:`~elka.dispatch.KeyDispatch`, so it can own key
    handlers (via :meth:`~elka.dispatch.KeyDispatch.on`) that the terminal
    delivers only while this element is the focused pane.
    """

    @abstractmethod
    def render(self, buf, rect):
        """Draw into ``buf`` within ``rect`` (a :class:`elka.buffer.Rect`)."""
        raise NotImplementedError

    def focused_leaf(self):
        """Return the element that should receive keys, or ``None``.

        A leaf is its own focused target. Container elements such as
        :class:`~elka.elements.split.HorizontalSplit` override this to descend
        into the focused pane, returning ``None`` when nothing is focused.
        """
        return self

    def focus_at(self, x, y):
        """Route a click at cell ``(x, y)`` into this element's focus model.

        Returns ``True`` if the point landed inside a focusable region (so a
        parent container knows the click was consumed). The default is a no-op
        returning ``False``; container elements such as
        :class:`~elka.elements.split.HorizontalSplit` override it to track and
        indicate which pane holds focus. The terminal calls this on the root
        element for every left-button press once
        :meth:`~elka.Terminal.enable_mouse` is on.
        """
        return False

    def clear_focus(self):
        """Recursively drop any focus indication. Default is a no-op."""

    def content_height(self, width):
        """Natural height in rows this element wants at ``width``.

        Returned as a row count; ``None`` means unknown/unbounded. A
        :class:`~elka.elements.scroll.Scroll` wrapper uses this to size its
        content and clamp scrolling to the last row. Elements that draw a
        variable number of rows (trees, lists) should override this; the
        default is ``None`` (the wrapper then falls back to the visible height
        plus the current offset).
        """
        return None


def resolve(value):
    """Return ``value()`` if it is callable, else ``value``.

    Lets element inputs (ratios, task lists, trees) be either a constant or a
    provider function that is re-invoked every frame.
    """
    return value() if callable(value) else value
