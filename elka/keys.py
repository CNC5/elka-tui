"""Parse raw terminal input bytes into human-readable key tokens.

``parse(data)`` turns a chunk of bytes read from stdin (in cbreak/raw mode) into
a list of key-name strings such as ``"up"``, ``"enter"``, ``"ctrl-a"``,
``"escape"``, or a printable character like ``"q"``.

When mouse reporting is enabled (see :meth:`elka.Terminal.enable_mouse`) the
list may also contain :class:`MouseEvent` objects, interleaved in input order.

Handlers are registered against key names via :meth:`elka.Terminal.on` and
against mouse events via :meth:`elka.Terminal.on_mouse`.
"""

from dataclasses import dataclass


@dataclass
class MouseEvent:
    """A single mouse report, with 0-indexed cell coordinates.

    :param x: column (0-indexed).
    :param y: row (0-indexed).
    :param button: ``"left"``, ``"middle"``, ``"right"``, ``"wheel_up"``, or
        ``"wheel_down"``.
    :param action: ``"press"``, ``"release"``, or ``"drag"`` (wheels only
        report ``"press"``).
    """

    x: int
    y: int
    button: str
    action: str


# Named special keys (also usable as constants, e.g. ``keys.UP``).
UP = "up"
DOWN = "down"
RIGHT = "right"
LEFT = "left"
HOME = "home"
END = "end"
PAGE_UP = "pageup"
PAGE_DOWN = "pagedown"
INSERT = "insert"
DELETE = "delete"
ENTER = "enter"
TAB = "tab"
BACKSPACE = "backspace"
ESCAPE = "escape"
SPACE = "space"

# Final CSI byte -> key name, for ``ESC [ <final>`` sequences.
_CSI_FINAL = {
    "A": UP, "B": DOWN, "C": RIGHT, "D": LEFT, "H": HOME, "F": END,
}
# Numeric CSI ``ESC [ <n> ~`` sequences.
_CSI_TILDE = {
    "1": HOME, "2": INSERT, "3": DELETE, "4": END,
    "5": PAGE_UP, "6": PAGE_DOWN, "7": HOME, "8": END,
    "15": "f5", "17": "f6", "18": "f7", "19": "f8",
    "20": "f9", "21": "f10", "23": "f11", "24": "f12",
}
# SS3 ``ESC O <final>`` sequences (function keys).
_SS3_FINAL = {"P": "f1", "Q": "f2", "R": "f3", "S": "f4"}

# Low two bits of an SGR mouse code -> button (unless a wheel/motion bit is set).
_MOUSE_BUTTONS = {0: "left", 1: "middle", 2: "right"}


def _mouse_event(body, final):
    """Decode an SGR mouse CSI body (``<b;x;y``) into a :class:`MouseEvent`.

    ``final`` is ``"M"`` for a press/drag and ``"m"`` for a release. Returns
    ``None`` if the body is malformed.
    """
    try:
        code, col, row = (int(part) for part in body[1:].split(";"))
    except ValueError:
        return None
    if code & 64:  # wheel: low bit picks the direction; wheels only "press"
        button = "wheel_up" if code & 1 == 0 else "wheel_down"
        action = "press"
    else:
        button = _MOUSE_BUTTONS.get(code & 0b11, "release")
        action = "drag" if code & 32 else ("press" if final == "M" else "release")
    return MouseEvent(col - 1, row - 1, button, action)  # SGR is 1-indexed


def _utf8_len(first):
    """Number of bytes in a UTF-8 sequence given its leading byte."""
    if first < 0x80:
        return 1
    if first >> 5 == 0b110:
        return 2
    if first >> 4 == 0b1110:
        return 3
    if first >> 3 == 0b11110:
        return 4
    return 1


def parse(data):
    """Turn a ``bytes`` chunk into a list of key-name tokens."""
    keys = []
    i, n = 0, len(data)
    while i < n:
        b = data[i]

        # --- escape sequences ------------------------------------------
        if b == 0x1B:
            if i + 1 < n and data[i + 1] == 0x5B:  # ESC [
                j = i + 2
                while j < n and not (0x40 <= data[j] <= 0x7E):
                    j += 1
                if j < n:
                    body = data[i + 2 : j].decode("latin-1")
                    final = chr(data[j])
                    if body[:1] == "<":  # SGR mouse report
                        ev = _mouse_event(body, final)
                        keys.append(ev if ev is not None else ESCAPE)
                    elif final == "~":
                        keys.append(_CSI_TILDE.get(body, ESCAPE))
                    else:
                        keys.append(_CSI_FINAL.get(final, ESCAPE))
                    i = j + 1
                    continue
                keys.append(ESCAPE)
                i = n
                continue
            if i + 1 < n and data[i + 1] == 0x4F:  # ESC O  (SS3)
                if i + 2 < n:
                    keys.append(_SS3_FINAL.get(chr(data[i + 2]), ESCAPE))
                    i += 3
                    continue
            keys.append(ESCAPE)
            i += 1
            continue

        # --- control characters ----------------------------------------
        if b in (0x0D, 0x0A):
            keys.append(ENTER)
        elif b == 0x09:
            keys.append(TAB)
        elif b in (0x7F, 0x08):
            keys.append(BACKSPACE)
        elif b == 0x20:
            keys.append(SPACE)
        elif 1 <= b <= 26:  # Ctrl-A .. Ctrl-Z (tab/enter handled above)
            keys.append("ctrl-" + chr(b + 96))
        elif b == 0:
            keys.append("ctrl-space")
        else:
            # --- printable (ASCII or UTF-8 multibyte) ------------------
            length = _utf8_len(b)
            chunk = data[i : i + length]
            try:
                keys.append(chunk.decode("utf-8"))
            except UnicodeDecodeError:
                keys.append(chunk[:1].decode("latin-1"))
            i += length
            continue

        i += 1

    return keys
