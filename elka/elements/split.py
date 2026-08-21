"""Horizontal split: two stacked panes separated by a horizontal divider."""

from .. import ansi
from .base import Element, resolve

# Marker drawn at the divider's left end pointing at the focused pane.
_FOCUS_MARKERS = {0: "▲", 1: "▼"}


class HorizontalSplit(Element):
    """Stack two elements vertically, split by a horizontal line.

    :param top: element drawn in the upper region.
    :param bottom: element drawn in the lower region.
    :param ratio: fraction of the height given to ``top``. May be a float or a
        ``() -> float`` provider (its input class is ``float``); resolved every
        frame and clamped to ``[0, 1]``.
    :param divider: if true, reserve one row between the panes for a line.
    :param divider_char: glyph used for the divider line.
    :param focus_style: SGR prefix used to emphasise the divider of the pane
        that holds focus. Defaults to bold.

    A pane gains focus when clicked (see :meth:`focus_at`, driven by the
    terminal's mouse handling) or when :attr:`focused` is set directly. Focus
    is shown on the divider, so ``divider=True`` is needed for the indicator to
    be visible.
    """

    def __init__(
        self,
        top,
        bottom,
        ratio=0.5,
        divider=False,
        divider_char="─",
        focus_style=ansi.sgr(1),
    ):
        self.top = top
        self.bottom = bottom
        self.ratio = ratio
        self.divider = divider
        self.divider_char = divider_char
        self.focus_style = focus_style
        self.focused = None          # 0 = top, 1 = bottom, None = neither
        self._rect = None            # whole region, recorded for hit-testing
        self._split_y = None         # first row belonging to the bottom pane

    def render(self, buf, rect):
        if rect.height <= 0 or rect.width <= 0:
            return

        self._rect = rect
        ratio = max(0.0, min(1.0, float(resolve(self.ratio))))

        divider_rows = 1 if self.divider and rect.height >= 3 else 0
        usable = rect.height - divider_rows
        top_h = round(usable * ratio)

        top_rect, rest = rect.split_horizontal(top_h)
        self.top.render(buf, top_rect)

        if divider_rows:
            focused = self.focused is not None
            style = self.focus_style if focused else ""
            buf.hline(rest.x, rest.y, rest.width, self.divider_char, style)
            if focused:
                buf.set(rest.x, rest.y, _FOCUS_MARKERS[self.focused], style)
            _, bottom_rect = rest.split_horizontal(1)
        else:
            bottom_rect = rest

        self._split_y = bottom_rect.y
        self.bottom.render(buf, bottom_rect)

    # -- focus ---------------------------------------------------------------
    def focus_at(self, x, y):
        r = self._rect
        if r is None or not (
            r.x <= x < r.x + r.width and r.y <= y < r.y + r.height
        ):
            return False

        top_hit = y < self._split_y
        self.focused = 0 if top_hit else 1
        focused, other = (
            (self.top, self.bottom) if top_hit else (self.bottom, self.top)
        )
        focused.focus_at(x, y)   # recurse so nested splits focus their pane too
        other.clear_focus()      # keep a single focus path through the tree
        return True

    def focus_pane(self, index):
        """Focus pane ``index`` (``0`` top, ``1`` bottom); clear the other pane.

        A convenient way to move focus from the keyboard, keeping the single
        focus path even across nested splits.
        """
        self.focused = index
        (self.bottom if index == 0 else self.top).clear_focus()

    def clear_focus(self):
        self.focused = None
        self.top.clear_focus()
        self.bottom.clear_focus()

    def focused_leaf(self):
        if self.focused is None:
            return None
        pane = self.top if self.focused == 0 else self.bottom
        return pane.focused_leaf()
