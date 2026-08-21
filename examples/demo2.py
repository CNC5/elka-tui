"""Interactive demo: a task list above a Text log driven by the push API.

Run in a real terminal::

    python examples/demo2.py

The top pane is a :class:`TaskList` (pull model -- its provider reads mutable
state every frame). The bottom pane is a :class:`Text` in *push* mode: instead
of a provider, the app calls ``append``/``set``/``delete_first`` on it to grow
and trim a scrolling log.

Keys act on the focused pane (the divider marks it):
    up / down / j / k   task list: move selection; log: scroll
    space               task list: advance the selected task (logs a line)
    c                   log: clear it (Text.set)
    x                   log: drop the oldest line (Text.delete_first)

App-wide keys (any focus):
    tab                 switch focus between the panes
    q / esc             quit

Mouse:
    click a pane        focus it
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from elka import HorizontalSplit, Scroll, Task, TaskList, Text, terminal

NAMES = ["build", "test", "package"]
state = {"selected": 0, "progress": {n: 0 for n in NAMES}, "running": True}


def tasks():
    rows = []
    for i, name in enumerate(NAMES):
        marker = "> " if i == state["selected"] else "  "
        rows.append(Task(marker + name, state["progress"][name], 100))
    return rows


tasklist = TaskList(tasks, title="Tasks  (Tab switches panes, q quits)")

# Text in push mode: no provider, so the app drives it directly. Seed one line,
# then Scroll it so a long log stays reachable.
log = Text(text="log ready.")
log_view = Scroll(log)

layout = HorizontalSplit(tasklist, log_view, ratio=0.5, divider=True)
layout.focus_pane(0)
terminal.attach(layout)


def move(delta):
    state["selected"] = (state["selected"] + delta) % len(NAMES)


def advance(_key):
    name = NAMES[state["selected"]]
    new = min(100, state["progress"][name] + 10)
    state["progress"][name] = new
    log.append(f"{name}: {new}%")       # push a line onto the Text
    log_view.to_bottom()                 # keep the newest line in view


def clear_log(_key):
    log.set([])                          # replace all content (empties it)
    log.append("log cleared.")


def drop_oldest(_key):
    log.delete_first(1)                  # trim from the top


# Pane-scoped keys: fire only while that pane is focused.
tasklist.on("up", lambda k: move(-1))
tasklist.on("k", lambda k: move(-1))
tasklist.on("down", lambda k: move(1))
tasklist.on("j", lambda k: move(1))
tasklist.on("space", advance)

log_view.on("up", lambda k: log_view.scroll_by(-1))
log_view.on("k", lambda k: log_view.scroll_by(-1))
log_view.on("down", lambda k: log_view.scroll_by(1))
log_view.on("j", lambda k: log_view.scroll_by(1))
log_view.on("c", clear_log)
log_view.on("x", drop_oldest)

# App-wide keys.
terminal.on("tab", lambda k: layout.focus_pane(0 if layout.focused else 1))
terminal.on("q", lambda k: state.update(running=False))
terminal.on("escape", lambda k: state.update(running=False))

terminal.enable_mouse()

with terminal:
    while state["running"]:
        terminal.render()
        terminal.poll_input(timeout=0.1)
