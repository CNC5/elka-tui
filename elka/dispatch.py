"""Key-handler registration shared by the terminal and individual elements.

:class:`KeyDispatch` is a mixin that stores handlers keyed by key name plus a
list of catch-all handlers, and dispatches a key-name token to them. The
:class:`~elka.Terminal` mixes it in for app-wide handlers; every
:class:`~elka.elements.base.Element` mixes it in too, so a focused pane can own
handlers that fire only while it holds focus.
"""


class KeyDispatch:
    """Register key handlers on an object and dispatch key tokens to them.

    Handler storage is created lazily in ``__dict__`` on first use, so mixing
    this into a class needs no cooperating ``__init__``.
    """

    def _key_map(self):
        handlers = self.__dict__.get("_key_handlers")
        if handlers is None:
            handlers = self.__dict__["_key_handlers"] = {}
        return handlers

    def _any_list(self):
        anys = self.__dict__.get("_any_handlers")
        if anys is None:
            anys = self.__dict__["_any_handlers"] = []
        return anys

    def on(self, key, handler=None):
        """Register ``handler`` for a key name (e.g. ``"q"``, ``"up"``, ``"enter"``).

        The handler is called as ``handler(key)``. Usable directly or as a
        decorator::

            widget.on("q", quit)

            @widget.on("up")
            def move_up(key):
                ...
        """
        def register(fn):
            self._key_map().setdefault(key, []).append(fn)
            return fn

        return register if handler is None else register(handler)

    def on_any(self, handler=None):
        """Register a catch-all handler invoked for every key (after specific ones)."""
        def register(fn):
            self._any_list().append(fn)
            return fn

        return register if handler is None else register(handler)

    def dispatch_key(self, key):
        """Dispatch ``key`` to specific handlers then catch-alls.

        Returns ``True`` if at least one handler ran.
        """
        handled = False
        for fn in self._key_map().get(key, ()):
            fn(key)
            handled = True
        for fn in list(self._any_list()):
            fn(key)
            handled = True
        return handled
