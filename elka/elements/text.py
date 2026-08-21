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
    """

    def __init__(self, provider=None, text=None):
        self.provider = provider
        self._lines = self._as_lines(text) if text is not None else []

    # -- content -------------------------------------------------------------
    @staticmethod
    def _as_lines(value):
        """Normalize a str (split on newlines) or iterable of lines to a list."""
        if isinstance(value, str):
            return value.split("\n")
        return [str(line) for line in value]

    def _current(self):
        if self.provider is not None:
            return self._as_lines(resolve(self.provider))
        return self._lines

    def _require_push(self):
        if self.provider is not None:
            raise RuntimeError("push methods unavailable while a provider is set")

    # -- push API ------------------------------------------------------------
    def set(self, text):
        """Replace all content with ``text`` (str or list of lines)."""
        self._require_push()
        self._lines = self._as_lines(text)

    def append(self, text):
        """Append ``text`` (str or list of lines) after the current content."""
        self._require_push()
        self._lines.extend(self._as_lines(text))

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
        for i, line in enumerate(self._current()):
            row = rect.y + i
            if row >= bottom:
                break
            buf.text(rect.x, row, line, max_width=rect.width)
