"""Raw ANSI escape-code helpers.

Everything here returns plain strings; nothing writes to the terminal. The
``Terminal`` is responsible for actually emitting these.
"""

ESC = "\x1b"
CSI = ESC + "["

# Screen / cursor control ----------------------------------------------------
ENTER_ALT_SCREEN = CSI + "?1049h"
LEAVE_ALT_SCREEN = CSI + "?1049l"
HIDE_CURSOR = CSI + "?25l"
SHOW_CURSOR = CSI + "?25h"
CLEAR_SCREEN = CSI + "2J"
RESET_STYLE = CSI + "0m"

# Mouse reporting: button-press/release + SGR extended coordinates (mode 1006,
# so columns/rows past 223 report correctly). Enabling this takes over the
# terminal's own click-to-select, so it is opt-in via ``Terminal.enable_mouse``.
ENABLE_MOUSE = CSI + "?1000h" + CSI + "?1006h"
DISABLE_MOUSE = CSI + "?1006l" + CSI + "?1000l"


def move(x, y):
    """Cursor-move to a 0-indexed ``(x, y)``; ANSI is 1-indexed, so add one."""
    return f"{CSI}{y + 1};{x + 1}H"


def sgr(*codes):
    """Build an SGR (Select Graphic Rendition) sequence, e.g. ``sgr(1, 31)``."""
    return CSI + ";".join(str(c) for c in codes) + "m"


# Colour / style helpers -----------------------------------------------------
# These return plain SGR strings, so they drop straight into any ``style=``
# argument (cell styles, ``Task(..., style=...)``, ``TreeNode(..., style=...)``).

# Ready-to-use foreground colours, from the base-8 palette.
BLACK = sgr(30)
RED = sgr(31)
GREEN = sgr(32)
YELLOW = sgr(33)
BLUE = sgr(34)
MAGENTA = sgr(35)
CYAN = sgr(36)
WHITE = sgr(37)

# Text attributes.
BOLD = sgr(1)
DIM = sgr(2)
ITALIC = sgr(3)
UNDERLINE = sgr(4)


def fg(code):
    """256-colour foreground SGR sequence (``code`` in 0-255)."""
    return sgr(38, 5, code)


def bg(code):
    """256-colour background SGR sequence (``code`` in 0-255)."""
    return sgr(48, 5, code)
