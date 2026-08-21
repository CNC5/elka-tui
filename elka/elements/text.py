"""Text element: display lines of text via a pull provider or a push API."""

from .base import Element, resolve


class Text(Element):
    """Render lines of text, one per row, truncated to the region width.

    Two mutually exclusive modes:

    - Pull: pass ``provider`` (``() -> str | list[str]``), re-invoked every
      frame like the other elements. A constant str/list is also accepted.
    - Push: omit ``provider`` and drive the content with :meth:`set`,
      :meth:`append`, :meth:`delete_last`, :meth:`delete_first`.

    Content may be given as a single string (split on ``"\\n"``) or a list of
    lines. Calling a push method while a ``provider`` is set raises
    ``RuntimeError``.

    Lines may be coloured: pass ``style`` (an SGR prefix such as ``ansi.RED``)
    to colour every line of a call, or give a ``(text, style)`` tuple in place
    of a plain line to colour that line individually.
    """

    def __init__(self, provider=None, text=None, style=""):
        self.provider = provider
        self._lines = self._as_lines(text, style) if text is not None else []

    # -- content -------------------------------------------------------------
    @staticmethod
    def _as_lines(value, style=""):
        """Normalize content to a list of ``(text, style)`` tuples.

        ``value`` is a str (split on newlines) or an iterable whose items are
        either plain lines or ``(text, style)`` tuples. ``style`` is the default
        applied to lines that don't carry their own.
        """
        if isinstance(value, str):
            return [(line, style) for line in value.split("\n")]
        lines = []
        for item in value:
            if isinstance(item, tuple):
                text, item_style = item
                lines.append((str(text), item_style))
            else:
                lines.append((str(item), style))
        return lines

    def _current(self):
        """Current content as a list of ``(text, style)`` tuples."""
        if self.provider is not None:
            return self._as_lines(resolve(self.provider))
        return self._lines

    def _require_push(self):
        if self.provider is not None:
            raise RuntimeError("push methods unavailable while a provider is set")

    # -- push API ------------------------------------------------------------
    def set(self, text, style=""):
        """Replace all content with ``text`` (str or list of lines)."""
        self._require_push()
        self._lines = self._as_lines(text, style)

    def append(self, text, style=""):
        """Append ``text`` (str or list of lines) after the current content."""
        self._require_push()
        self._lines.extend(self._as_lines(text, style))

    def delete_last(self, n=1):
        """Remove the last ``n`` lines (clamped; no-op when ``n <= 0``)."""
        self._require_push()
        if n > 0:
            del self._lines[len(self._lines) - min(n, len(self._lines)):]

    def delete_first(self, n=1):
        """Remove the first ``n`` lines (clamped; no-op when ``n <= 0``)."""
        self._require_push()
        if n > 0:
            del self._lines[:n]

    # -- rendering -----------------------------------------------------------
    def content_height(self, width):
        return len(self._current())

    def render(self, buf, rect):
        if rect.height <= 0 or rect.width <= 0:
            return
        bottom = rect.y + rect.height
        for i, (line, style) in enumerate(self._current()):
            row = rect.y + i
            if row >= bottom:
                break
            buf.text(rect.x, row, line, style=style, max_width=rect.width)
