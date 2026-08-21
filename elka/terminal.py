"""The singleton terminal that owns the screen.

Usage::

    from elka import terminal
    terminal.attach(root_element)
    with terminal:              # start(): alt screen, hidden cursor, raw mode
        while running:
            terminal.poll_input()   # dispatch keystrokes to handlers
            terminal.render()       # caller-driven; one frame per call

Both input and rendering are caller-driven: nothing happens on its own. Each
``render()`` pulls fresh values from the attached element tree, draws into an
off-screen buffer, diffs against the last displayed frame, and emits ANSI only
for changed cells. Each ``poll_input()`` reads any pending keystrokes (raw,
non-blocking) and dispatches them to registered handlers.
"""

import atexit
import os
import select
import signal
import sys

from . import ansi, keys
from .buffer import Buffer, Rect
from .dispatch import KeyDispatch


class Terminal(KeyDispatch):
    """Owns stdout, terminal modes, and the attached root element.

    This is a singleton: construct via :meth:`instance` (or just import the
    module-level ``terminal``). Direct construction returns the same object.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    @classmethod
    def instance(cls):
        return cls()

    def _init(self):
        self._out = sys.stdout
        self._in = sys.stdin
        self._out_fd = None
        self._in_fd = None
        self._saved_termios = None
        self._started = False
        self._root = None
        self._front = None          # last displayed frame
        self._back = Buffer()       # frame being drawn
        self._is_tty = self._out.isatty()
        self._key_handlers = {}     # key name -> list[callable]
        self._any_handlers = []     # callables invoked for every key
        self._mouse_handlers = []   # callables invoked for every mouse event
        self._mouse_enabled = False

    # -- composition ---------------------------------------------------------
    def attach(self, element):
        """Set the root element. Compose multiple panes via ``HorizontalSplit``."""
        self._root = element
        return element

    # -- input handling ------------------------------------------------------
    # ``on`` / ``on_any`` come from KeyDispatch and register app-wide handlers.
    # Handlers registered on an element instead fire only while it is focused;
    # see :meth:`_dispatch_key`.
    def on_mouse(self, handler=None):
        """Register a handler invoked for every :class:`~elka.keys.MouseEvent`.

        The handler is called as ``handler(event)``. Mouse events only arrive
        after :meth:`enable_mouse`. Independently of any handler registered
        here, a left-button press is routed into the attached element tree via
        ``root.focus_at(x, y)`` for click-to-focus. Usable directly or as a
        decorator.
        """
        def register(fn):
            self._mouse_handlers.append(fn)
            return fn

        return register if handler is None else register(handler)

    def enable_mouse(self, enabled=True):
        """Turn mouse reporting on (or off). Off by default.

        Enabling hands click/scroll/drag reports to the app but takes over the
        terminal's own click-to-select, so it is opt-in. Safe to call before or
        after :meth:`start`; the escape sequence is emitted immediately when the
        terminal is already running. Restored automatically on :meth:`stop`.
        """
        self._mouse_enabled = enabled
        if self._started and self._is_tty:
            self._out.write(ansi.ENABLE_MOUSE if enabled else ansi.DISABLE_MOUSE)
            self._out.flush()
        return self

    def poll_input(self, timeout=0):
        """Read pending input events and dispatch them to handlers.

        With ``timeout=0`` (default) this is non-blocking; a positive ``timeout``
        waits up to that many seconds for input, which is a convenient way to
        pace a loop without a separate ``sleep`` (events are never dropped).
        Returns the list of events read (key names, plus
        :class:`~elka.keys.MouseEvent` objects when mouse reporting is on).
        No-op (``[]``) when stdin isn't a TTY.
        """
        events = self.read_keys(timeout=timeout)
        for event in events:
            if isinstance(event, keys.MouseEvent):
                self._dispatch_mouse(event)
            else:
                self._dispatch_key(event)
        return events

    def _dispatch_key(self, key):
        # The focused pane gets first crack at the key; then app-wide handlers
        # registered on the terminal run (so keys like quit work regardless of
        # focus). When no pane is focused, only the app-wide handlers run.
        focused = self._root.focused_leaf() if self._root is not None else None
        if focused is not None:
            focused.dispatch_key(key)
        self.dispatch_key(key)

    def _dispatch_mouse(self, event):
        for fn in self._mouse_handlers:
            fn(event)
        # Built-in click-to-focus: hand a left press to the element tree.
        if (
            event.action == "press"
            and event.button == "left"
            and self._root is not None
        ):
            self._root.focus_at(event.x, event.y)

    def read_keys(self, timeout=0):
        """Read and parse available keys, waiting up to ``timeout`` seconds.

        ``timeout=0`` returns immediately (non-blocking); ``timeout=None`` blocks
        until at least one key is available. Dispatches nothing — use
        :meth:`poll_input` for that.
        """
        if not self._is_tty or self._in_fd is None:
            return []

        ready, _, _ = select.select([self._in_fd], [], [], timeout)
        if not ready:
            return []

        data = os.read(self._in_fd, 1024)
        if not data:
            return []
        return keys.parse(data)

    # -- lifecycle -----------------------------------------------------------
    def start(self):
        """Enter the alternate screen, hide the cursor, put tty in cbreak mode.

        A no-op when stdout is not a TTY (e.g. piped output), so callers can run
        headless without special-casing.
        """
        if self._started or not self._is_tty:
            self._started = self._started or not self._is_tty
            return self
        self._started = True

        import termios
        import tty

        self._out_fd = self._out.fileno()
        self._in_fd = self._in.fileno()
        # cbreak on the input fd: unbuffered, no echo, but keeps ISIG so Ctrl-C
        # still raises SIGINT (handled below to restore the terminal on exit).
        self._saved_termios = termios.tcgetattr(self._in_fd)
        tty.setcbreak(self._in_fd)

        atexit.register(self.stop)
        self._install_signal_handlers()

        self._out.write(ansi.ENTER_ALT_SCREEN + ansi.HIDE_CURSOR + ansi.CLEAR_SCREEN)
        if self._mouse_enabled:
            self._out.write(ansi.ENABLE_MOUSE)
        self._out.flush()
        self._front = None          # force a full repaint on first frame
        return self

    def stop(self):
        """Restore the terminal. Idempotent and safe to call from atexit."""
        if not self._started or not self._is_tty:
            self._started = False
            return
        self._started = False

        if self._saved_termios is not None and self._in_fd is not None:
            import termios

            termios.tcsetattr(self._in_fd, termios.TCSADRAIN, self._saved_termios)
            self._saved_termios = None

        mouse_off = ansi.DISABLE_MOUSE if self._mouse_enabled else ""
        self._out.write(
            mouse_off + ansi.RESET_STYLE + ansi.SHOW_CURSOR + ansi.LEAVE_ALT_SCREEN
        )
        self._out.flush()

    def _install_signal_handlers(self):
        def handler(signum, frame):
            self.stop()
            # Restore default behaviour and re-raise so exit codes are correct.
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, handler)
            except ValueError:
                # Not on the main thread; skip signal handling.
                pass

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False

    # -- rendering -----------------------------------------------------------
    def size(self):
        """Current ``(width, height)`` of the terminal."""
        try:
            cols, rows = os.get_terminal_size(self._out_fd or 1)
        except OSError:
            cols, rows = 80, 24
        return cols, rows

    def render(self):
        """Draw one frame. Caller-driven; typically called in a loop."""
        if not self._is_tty:
            return

        width, height = self.size()
        self._back.resize(width, height)
        self._back.clear()

        if self._root is not None:
            self._root.render(self._back, Rect(0, 0, width, height))

        self._flush(self._back.diff(self._front))

        # Swap buffers: what we just drew becomes the reference for next diff.
        self._front, self._back = self._back, self._front or Buffer()

    def _flush(self, changes):
        """Emit ANSI for changed cells, coalescing adjacent cells on a row."""
        if not changes:
            return

        parts = []
        last_style = None
        prev = None  # (x, y) of the previously written cell
        for x, y, cell in changes:
            if prev != (x - 1, y):
                parts.append(ansi.move(x, y))
            if cell.style != last_style:
                parts.append(ansi.RESET_STYLE + cell.style)
                last_style = cell.style
            parts.append(cell.char)
            prev = (x, y)

        parts.append(ansi.RESET_STYLE)
        self._out.write("".join(parts))
        self._out.flush()


# Module-level singleton for convenient importing.
terminal = Terminal.instance()
