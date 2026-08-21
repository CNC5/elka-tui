"""Interactive demo: task list over a tree, with keyboard handling.

Run in a real terminal::

    python examples/demo.py

Keys act on the focused pane (the divider marks it):
    tab                 switch focus between the panes
    up / down / j / k   task list: move selection; tree: scroll
    space               task list: advance the selected task's progress
    pgup / pgdn         tree: scroll by a page

App-wide keys (any focus):
    tab, q / esc        switch focus / quit

Mouse:
    click a pane        focus it
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from elka import HorizontalSplit, Scroll, Task, TaskList, Tree, TreeNode, ansi, terminal

# Mutable state the provider closures read from every frame.
NAMES = ["build", "test", "package"]
state = {"selected": 0, "progress": {n: 0 for n in NAMES}, "running": True}


def tasks():
    rows = []
    for i, name in enumerate(NAMES):
        marker = "> " if i == state["selected"] else "  "
        progress = state["progress"][name]
        # Colour by progress: green once complete, yellow while in flight.
        style = ansi.GREEN if progress >= 100 else ansi.YELLOW if progress else ""
        rows.append(Task(marker + name, progress, 100, style=style))
    return rows


def tree():
    # Deliberately taller than its pane so the Scroll wrapper has work to do.
    return TreeNode(
        "project",
        [
            TreeNode(
                "src",
                [TreeNode(f"module_{i:02d}.py", style=ansi.CYAN) for i in range(20)],
                style=ansi.BOLD,
            ),
            TreeNode(
                "tests",
                [TreeNode("test_main.py"), TreeNode("test_util.py")],
                style=ansi.BOLD,
            ),
            TreeNode("README.md", style=ansi.GREEN),
        ],
    )


def move(delta):
    state["selected"] = (state["selected"] + delta) % len(NAMES)


def advance(_key):
    name = NAMES[state["selected"]]
    state["progress"][name] = min(100, state["progress"][name] + 10)


def quit_(_key):
    state["running"] = False


tasklist = TaskList(tasks, title="Tasks  (Tab switches panes, q quits)")
forest = Scroll(Tree(tree))
layout = HorizontalSplit(tasklist, forest, ratio=0.4, divider=True)
layout.focus_pane(0)            # start with the task list focused
terminal.attach(layout)

# Pane-scoped keys: registered on an element, they fire only while it is
# focused, so up/down means "select" in the task list and "scroll" in the tree.
tasklist.on("up", lambda k: move(-1))
tasklist.on("k", lambda k: move(-1))
tasklist.on("down", lambda k: move(1))
tasklist.on("j", lambda k: move(1))
tasklist.on("space", advance)

forest.on("up", lambda k: forest.scroll_by(-1))
forest.on("k", lambda k: forest.scroll_by(-1))
forest.on("down", lambda k: forest.scroll_by(1))
forest.on("j", lambda k: forest.scroll_by(1))
forest.on("pageup", lambda k: forest.page_up())
forest.on("pagedown", lambda k: forest.page_down())

# App-wide keys: registered on the terminal, they fire regardless of focus.
terminal.on("tab", lambda k: layout.focus_pane(0 if layout.focused else 1))
terminal.on("q", quit_)
terminal.on("escape", quit_)

# Click a pane (or press Tab) to focus it; the split marks it on the divider.
terminal.enable_mouse()

with terminal:
    while state["running"]:
        terminal.render()
        # Block up to 0.1s for a key, then loop to repaint. Keeps CPU near idle
        # while staying responsive; no keystrokes are dropped.
        terminal.poll_input(timeout=0.1)
