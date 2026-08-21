# elka

A small, stdlib-only Python TUI package. A singleton **terminal** owns the
screen; **elements** are attached to it and repainted on demand.

Data-driven elements take a **provider function** that is re-invoked every
frame — so you update the UI just by mutating whatever the provider reads. No
third-party dependencies; rendering is flicker-free (off-screen cell buffer +
diff) and **caller-driven** (you call `terminal.render()`). Keyboard input is
captured directly (raw, non-blocking) and dispatched to handler functions you
register.

## Elements

- `HorizontalSplit(top, bottom, ratio=0.5, divider=False)` — two stacked panes;
  `ratio` may be a float or a `() -> float` provider. Nest for multi-pane
  layouts. Clicking a pane focuses it; see [Mouse & focus](#mouse--focus).
- `TaskList(provider, title=None, bar_width=20)` — `provider() -> list[Task]`,
  where `Task(name, current=None, total=None, style="")` draws a progress bar
  when both `current` and `total` are set; `style` colours the whole row.
- `Tree(provider)` — `provider() -> TreeNode | list[TreeNode]`, where
  `TreeNode(label, children=[], expanded=True, style="")`; `style` colours the
  node's label (branch glyphs stay in the default colour).
- `Text(provider=None, text=None, style="")` — one line of text per row,
  truncated to the region width. Either **pull** (pass `provider`) or **push**
  (drive it with method calls). Lines can be coloured. See [Text](#text).
- `Scroll(child, offset=0)` — a movable vertical window into any element whose
  content is taller than its region. See [Scrolling](#scrolling).

## Usage

```python
from elka import terminal, HorizontalSplit, TaskList, Task, Tree, TreeNode

state = {"done": 0, "running": True}
terminal.attach(HorizontalSplit(
    TaskList(lambda: [Task("build", state["done"], 100)], title="Tasks"),
    Tree(lambda: TreeNode("root", [TreeNode("src"), TreeNode("README")])),
    ratio=0.4, divider=True,
))

terminal.on("space", lambda k: state.update(done=min(100, state["done"] + 10)))
terminal.on("q", lambda k: state.update(running=False))

with terminal:                       # alt screen, hidden cursor, raw mode
    while state["running"]:
        terminal.render()            # one frame
        terminal.poll_input(0.1)     # dispatch keys; blocks up to 0.1s to pace
```

`with terminal:` enters the alternate screen and restores everything on exit
(including on Ctrl-C or exceptions). When stdout is not a TTY the terminal
no-ops so callers can run headless.

## Text

`Text` renders lines of text, one per row. Content is either a single string
(split on `"\n"`) or a list of lines. It works in one of two mutually exclusive
modes:

**Pull** — pass a `provider` (`() -> str | list[str]`), re-invoked every frame
like the other data-driven elements. A constant string or list is also accepted:

```python
from elka import Text, terminal

status = {"msg": "idle"}
terminal.attach(Text(lambda: f"status: {status['msg']}"))
```

**Push** — omit `provider` and drive the content directly. Handy for a log
where you append as events happen rather than re-deriving the whole view:

```python
log = Text()                 # push mode
log.set("first line")        # replace all content (str or list of lines)
log.append(["line 2", "line 3"])
log.delete_first(1)          # drop the oldest line
log.delete_last()            # drop the newest (n=1 by default)
```

`delete_first`/`delete_last` clamp to the available lines and no-op for `n <= 0`.
Calling a push method while a `provider` is set raises `RuntimeError`. `Text`
reports its `content_height`, so it scrolls inside a `Scroll` wrapper like
`Tree` and `TaskList`.

## Colour

Colour is applied through **style** strings — raw SGR escape prefixes attached
to cells. The `elka.ansi` module provides ready-to-use ones so you don't
hand-write escapes: foreground colours `BLACK`, `RED`, `GREEN`, `YELLOW`, `BLUE`,
`MAGENTA`, `CYAN`, `WHITE`; attributes `BOLD`, `DIM`, `ITALIC`, `UNDERLINE`; and
`fg(n)` / `bg(n)` for 256-colour indices.

```python
from elka import Task, TaskList, Text, Tree, TreeNode, ansi

# A task row, coloured by state.
TaskList(lambda: [Task("build", 100, 100, style=ansi.GREEN)])

# A tree node label (the ├─/└─ glyphs stay uncoloured).
Tree(lambda: TreeNode("src", [TreeNode("main.py", style=ansi.CYAN)]))

# Text: one colour for a whole call, or per line via (text, style) tuples.
log = Text()
log.append("connected", style=ansi.GREEN)
log.append([("warning", ansi.YELLOW), ("error", ansi.RED)])
```

Any style string works, so `ansi.BOLD + ansi.RED` combines attributes, and you
can pass your own SGR sequence built with `ansi.sgr(...)`.

## Scrolling

Elements clip to their region and truncate anything past the bottom. Wrap one
in `Scroll` to make the overflow reachable: it renders the child into an
off-screen buffer as tall as its content, then shows just a slice of it.

```python
from elka import Scroll, Tree, terminal

log = Scroll(Tree(big_tree_provider))    # wraps any element
terminal.attach(log)

terminal.on("down",     lambda k: log.scroll_by(1))
terminal.on("up",       lambda k: log.scroll_by(-1))
terminal.on("pagedown", lambda k: log.page_down())
terminal.on("pageup",   lambda k: log.page_up())
terminal.on("home",     lambda k: log.to_top())
terminal.on("end",      lambda k: log.to_bottom())
```

The wrapper owns the scroll position (`log.offset`) and clamps it to the
child's content every frame, so you never track content height yourself:
`scroll_by`/`scroll_to` stop at the first and last row, and `page_up`/
`page_down` move by the visible height. Clamping relies on the child reporting
its `content_height(width)`; the built-in `Tree`, `TaskList`, and `Text` do. `Scroll`
nests inside a `HorizontalSplit` pane like any other element.

## Keyboard input

Input is caller-driven like rendering. Register handlers, then call
`poll_input()` each frame to read and dispatch pending keystrokes. Handlers on
`terminal` are app-wide; the same `on`/`on_any` also work on any element, where
they fire only while that element is focused (see [Mouse &
focus](#mouse--focus)).

```python
terminal.on("up", lambda key: ...)      # a specific key
terminal.on("enter", handle_enter)      # handler receives the key name
terminal.on_any(lambda key: log(key))   # catch-all, runs after specific ones

@terminal.on("q")                        # also usable as a decorator
def quit(key):
    ...
```

- `poll_input(timeout=0)` — read + dispatch. `timeout=0` is non-blocking; a
  positive timeout waits that long for a key (handy to pace a loop without a
  separate `sleep`). Returns the key names read.
- `read_keys(timeout=0)` — read + parse without dispatching (`timeout=None`
  blocks until a key arrives).

Key names include printable characters (`"a"`, `"Q"`, `"é"`), `"up"`/`"down"`/
`"left"`/`"right"`, `"enter"`, `"tab"`, `"space"`, `"backspace"`, `"escape"`,
`"home"`/`"end"`/`"pageup"`/`"pagedown"`/`"insert"`/`"delete"`, `"f1"`–`"f12"`,
and `"ctrl-a"`–`"ctrl-z"`. Constants are also available (`elka.keys.UP`, etc.).
Ctrl-C keeps its default behavior (raises `SIGINT`, which cleanly restores the
terminal and exits) rather than arriving as a key.

## Mouse & focus

Mouse reporting is off by default (it takes over the terminal's own
click-to-select). Turn it on with `terminal.enable_mouse()`; from then on
`poll_input()` also dispatches `MouseEvent`s, and the list it returns may
contain them alongside key names.

```python
terminal.enable_mouse()
terminal.on_mouse(lambda e: log(e.x, e.y, e.button, e.action))
```

A `MouseEvent` has `x`/`y` (0-indexed cell coordinates), `button`
(`"left"`/`"middle"`/`"right"`/`"wheel_up"`/`"wheel_down"`), and `action`
(`"press"`/`"release"`/`"drag"`).

**Click-to-focus.** Independently of any `on_mouse` handler, a left-button
press is routed into the attached element tree as `root.focus_at(x, y)`.
A `HorizontalSplit` uses this to focus the pane under the click: it tracks the
focused pane in `split.focused` (`0` top, `1` bottom, `None` neither) and marks
it on the divider (`▲`/`▼`, drawn with `focus_style`), so `divider=True` makes
the indicator visible. Focus follows a single path through nested splits —
focusing one pane clears the others. You can also drive focus yourself:
`split.focus_pane(0)` / `split.focus_pane(1)` (handy from a keyboard handler),
or `split.clear_focus()`.

**Keys follow focus.** Elements are key dispatchers too, so a handler
registered on an element fires only while that element is the focused pane:

```python
tasklist.on("up", lambda k: move(-1))     # only when the task list is focused
tree_scroll.on("up", lambda k: tree_scroll.scroll_by(-1))  # only when the tree is
terminal.on("tab", switch_focus)          # on the terminal -> always fires
terminal.on("q", quit)
```

On each keystroke the focused leaf pane (resolved by walking the split-focus
path) is offered the key first, then the terminal's own app-wide handlers run —
so `up`/`down` can mean different things per pane while `q`/`tab` work
everywhere. When no pane is focused, only the app-wide handlers run.

## Try it

```
python examples/demo.py     # in a real terminal
python tests/test_elements.py
```
