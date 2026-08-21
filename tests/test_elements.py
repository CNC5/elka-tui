"""TTY-free logic tests: render into a Buffer and assert cell contents."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from elka import (
    Buffer,
    HorizontalSplit,
    Rect,
    Scroll,
    Task,
    TaskList,
    Text,
    Tree,
    TreeNode,
    ansi,
    keys,
)
from elka.buffer import Cell


def row_text(buf, y):
    return "".join(buf.get(x, y).char for x in range(buf.width)).rstrip()


def cell_style(buf, x, y):
    return buf.get(x, y).style


def render(element, width, height):
    buf = Buffer(width, height)
    element.render(buf, Rect(0, 0, width, height))
    return buf


# -- Buffer.diff -------------------------------------------------------------
def test_diff_reports_only_changes():
    prev = Buffer(3, 1)
    cur = Buffer(3, 1)
    cur.set(1, 0, "x")
    changes = cur.diff(prev)
    assert changes == [(1, 0, Cell("x", ""))]


def test_diff_full_on_resize():
    prev = Buffer(2, 1)
    cur = Buffer(3, 1)
    assert len(cur.diff(prev)) == 3  # dimensions differ -> every cell


# -- TaskList / progress-bar math -------------------------------------------
def test_task_without_progress_is_plain_name():
    buf = render(TaskList(lambda: [Task("idle")]), 40, 1)
    assert row_text(buf, 0) == "idle"


def test_progress_bar_half_full():
    buf = render(TaskList(lambda: [Task("build", 5, 10)], bar_width=10), 40, 1)
    assert row_text(buf, 0) == "build  [#####-----] 5/10"


def test_progress_bar_guards_zero_total():
    buf = render(TaskList(lambda: [Task("x", 0, 0)], bar_width=4), 40, 1)
    assert row_text(buf, 0) == "x  [----] 0/0"


def test_task_style_applies_to_whole_row():
    buf = render(TaskList(lambda: [Task("done", style=ansi.GREEN)]), 40, 1)
    assert row_text(buf, 0) == "done"
    assert [cell_style(buf, x, 0) for x in range(4)] == [ansi.GREEN] * 4


def test_title_occupies_first_row():
    buf = render(TaskList(lambda: [Task("a")], title="Tasks"), 40, 2)
    assert row_text(buf, 0) == "Tasks"
    assert row_text(buf, 1) == "a"


# -- Tree glyphs -------------------------------------------------------------
def test_tree_branch_glyphs():
    root = TreeNode(
        "root",
        [TreeNode("src", [TreeNode("main.py")]), TreeNode("README")],
    )
    buf = render(Tree(lambda: root), 40, 4)
    assert row_text(buf, 0) == "root"
    assert row_text(buf, 1) == "├─ src"
    assert row_text(buf, 2) == "│  └─ main.py"
    assert row_text(buf, 3) == "└─ README"


def test_tree_colors_label_not_glyphs():
    root = TreeNode("root", [TreeNode("src", style=ansi.GREEN)])
    buf = render(Tree(lambda: root), 40, 2)
    # branch glyphs stay unstyled; only the label carries the node's colour.
    assert cell_style(buf, 0, 1) == ""            # "└" glyph
    assert cell_style(buf, 3, 1) == ansi.GREEN    # "s" of "src"
    assert row_text(buf, 1) == "└─ src"


def test_tree_respects_collapsed():
    root = TreeNode("root", [TreeNode("a", [TreeNode("hidden")], expanded=False)])
    buf = render(Tree(lambda: root), 40, 4)
    assert row_text(buf, 0) == "root"
    assert row_text(buf, 1) == "└─ a"
    assert row_text(buf, 2) == ""  # child not rendered


# -- HorizontalSplit ---------------------------------------------------------
def test_split_partitions_by_ratio():
    top = TaskList(lambda: [Task("T")])
    bottom = TaskList(lambda: [Task("B")])
    buf = render(HorizontalSplit(top, bottom, ratio=0.5), 10, 4)
    assert row_text(buf, 0) == "T"
    assert row_text(buf, 2) == "B"


def test_split_ratio_accepts_callable():
    buf = render(
        HorizontalSplit(
            TaskList(lambda: [Task("T")]),
            TaskList(lambda: [Task("B")]),
            ratio=lambda: 0.25,
        ),
        10,
        4,
    )
    assert row_text(buf, 0) == "T"
    assert row_text(buf, 1) == "B"  # top gets 1 row (round(4*0.25))


def test_split_divider_line():
    buf = render(
        HorizontalSplit(
            TaskList(lambda: [Task("T")]),
            TaskList(lambda: [Task("B")]),
            ratio=0.5,
            divider=True,
        ),
        6,
        5,
    )
    # top_h = round((5-1)*0.5) = 2; divider on row 2
    assert row_text(buf, 2) == "─" * 6


# -- content_height ----------------------------------------------------------
def test_tasklist_content_height_counts_title_and_rows():
    tl = TaskList(lambda: [Task("a"), Task("b")], title="T")
    assert tl.content_height(40) == 3  # title + 2 rows


def test_tree_content_height_counts_visible_nodes():
    root = TreeNode("root", [TreeNode("a", [TreeNode("x")]), TreeNode("b")])
    assert Tree(lambda: root).content_height(40) == 4  # root, a, x, b


def test_tree_content_height_skips_collapsed():
    root = TreeNode("root", [TreeNode("a", [TreeNode("x")], expanded=False)])
    assert Tree(lambda: root).content_height(40) == 2  # root, a


# -- Scroll ------------------------------------------------------------------
def _numbered(n):
    return TaskList(lambda: [Task(str(i)) for i in range(n)])


def test_scroll_shows_top_window_by_default():
    buf = render(Scroll(_numbered(10)), 4, 3)
    assert [row_text(buf, y) for y in range(3)] == ["0", "1", "2"]


def test_scroll_offset_moves_the_window():
    buf = render(Scroll(_numbered(10), offset=4), 4, 3)
    assert [row_text(buf, y) for y in range(3)] == ["4", "5", "6"]


def test_scroll_clamps_to_last_row():
    s = Scroll(_numbered(10), offset=999)
    buf = render(s, 4, 3)
    # 10 rows, 3 visible -> max offset 7; window shows 7,8,9.
    assert [row_text(buf, y) for y in range(3)] == ["7", "8", "9"]
    assert s.offset == 7


def test_scroll_by_and_to_bottom_clamp():
    s = Scroll(_numbered(10))
    render(s, 4, 3)          # establishes clamp ceiling (max offset 7)
    s.scroll_by(-5)
    assert s.offset == 0     # cannot go above the top
    s.to_bottom()
    assert s.offset == 7


def test_scroll_paging_uses_view_height():
    s = Scroll(_numbered(20))
    render(s, 4, 5)          # 5 visible rows
    s.page_down()
    assert s.offset == 5
    s.page_down()
    assert s.offset == 10
    s.page_up()
    assert s.offset == 5


def test_scroll_preserves_child_styles():
    class Styled(TaskList):
        def render(self, buf, rect):
            buf.set(rect.x, rect.y + 1, "z", style="\x1b[31m")

    s = Scroll(Styled(lambda: [Task("a")] * 5), offset=1)
    buf = Buffer(4, 2)
    s.render(buf, Rect(0, 0, 4, 2))
    assert buf.get(0, 0).char == "z"
    assert buf.get(0, 0).style == "\x1b[31m"


# -- Text --------------------------------------------------------------------
def test_text_pull_from_string_splits_lines():
    buf = render(Text(lambda: "one\ntwo\nthree"), 20, 3)
    assert [row_text(buf, y) for y in range(3)] == ["one", "two", "three"]


def test_text_pull_from_list_of_lines():
    buf = render(Text(lambda: ["a", "b"]), 20, 2)
    assert [row_text(buf, y) for y in range(2)] == ["a", "b"]


def test_text_push_append_and_set():
    t = Text()
    t.append("first")
    t.append(["second", "third"])
    buf = render(t, 20, 3)
    assert [row_text(buf, y) for y in range(3)] == ["first", "second", "third"]
    t.set("only")
    buf = render(t, 20, 3)
    assert [row_text(buf, y) for y in range(3)] == ["only", "", ""]


def test_text_delete_last_and_first_clamp():
    t = Text(text=["a", "b", "c", "d"])
    t.delete_last(1)
    t.delete_first(1)
    assert [line for line, _ in t._current()] == ["b", "c"]
    t.delete_last(99)          # clamps, empties without error
    assert t._current() == []


def test_text_style_colors_all_pushed_lines():
    t = Text()
    t.append(["a", "b"], style=ansi.RED)
    buf = render(t, 20, 2)
    assert cell_style(buf, 0, 0) == ansi.RED
    assert cell_style(buf, 0, 1) == ansi.RED


def test_text_per_line_tuple_styles():
    t = Text(text=[("warn", ansi.YELLOW), "plain"])
    buf = render(t, 20, 2)
    assert cell_style(buf, 0, 0) == ansi.YELLOW
    assert cell_style(buf, 0, 1) == ""       # plain line keeps default style


def test_text_pull_tuple_lines_carry_style():
    buf = render(Text(lambda: [("hi", ansi.CYAN)]), 20, 1)
    assert row_text(buf, 0) == "hi"
    assert cell_style(buf, 0, 0) == ansi.CYAN


def test_text_truncates_long_line_to_width():
    buf = render(Text(lambda: "abcdefgh"), 4, 1)
    assert row_text(buf, 0) == "abcd"


def test_text_content_height_counts_lines():
    assert Text(lambda: "a\nb\nc").content_height(20) == 3
    assert Text(text=["x", "y"]).content_height(20) == 2


def test_text_push_methods_raise_with_provider():
    t = Text(lambda: "held")
    for call in (lambda: t.set("x"), lambda: t.append("x"),
                 t.delete_last, t.delete_first):
        try:
            call()
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected RuntimeError")


# -- keys.parse --------------------------------------------------------------
def test_parse_printable_and_enter():
    assert keys.parse(b"hi\r") == ["h", "i", "enter"]


def test_parse_arrow_keys():
    assert keys.parse(b"\x1b[A\x1b[B\x1b[C\x1b[D") == ["up", "down", "right", "left"]


def test_parse_ctrl_and_specials():
    assert keys.parse(b"\x01\t\x7f ") == ["ctrl-a", "tab", "backspace", "space"]


def test_parse_csi_tilde_and_lone_escape():
    assert keys.parse(b"\x1b[3~") == ["delete"]
    assert keys.parse(b"\x1b") == ["escape"]


def test_parse_utf8_multibyte():
    assert keys.parse("é".encode("utf-8")) == ["é"]


# -- keys.parse: mouse -------------------------------------------------------
def test_parse_mouse_press_and_release():
    assert keys.parse(b"\x1b[<0;12;5M") == [keys.MouseEvent(11, 4, "left", "press")]
    assert keys.parse(b"\x1b[<0;12;5m") == [keys.MouseEvent(11, 4, "left", "release")]


def test_parse_mouse_buttons_wheel_and_drag():
    assert keys.parse(b"\x1b[<2;1;1M")[0] == keys.MouseEvent(0, 0, "right", "press")
    assert keys.parse(b"\x1b[<64;3;4M")[0] == keys.MouseEvent(2, 3, "wheel_up", "press")
    assert keys.parse(b"\x1b[<65;3;4M")[0] == keys.MouseEvent(2, 3, "wheel_down", "press")
    assert keys.parse(b"\x1b[<32;9;9M")[0] == keys.MouseEvent(8, 8, "left", "drag")


def test_parse_mouse_interleaved_with_keys():
    assert keys.parse(b"a\x1b[<0;2;2Mb") == [
        "a",
        keys.MouseEvent(1, 1, "left", "press"),
        "b",
    ]


# -- HorizontalSplit focus ---------------------------------------------------
def _split(divider=True):
    return HorizontalSplit(
        TaskList(lambda: [Task("T")]),
        TaskList(lambda: [Task("B")]),
        ratio=0.5,
        divider=divider,
    )


def test_focus_at_selects_pane_by_row():
    s = _split()
    render(s, 6, 5)                 # top rows 0-1, divider row 2, bottom rows 3-4
    assert s.focus_at(0, 0) is True
    assert s.focused == 0
    assert s.focus_at(0, 4) is True
    assert s.focused == 1


def test_focus_at_outside_region_is_not_consumed():
    s = _split()
    render(s, 6, 5)
    assert s.focus_at(0, 99) is False
    assert s.focused is None        # unchanged


def test_focus_indicator_drawn_on_divider():
    s = _split()
    render(s, 6, 5)
    s.focus_at(0, 4)                # focus the bottom pane
    buf = render(s, 6, 5)
    assert buf.get(0, 2).char == "▼"          # marker points down
    assert buf.get(0, 2).style == s.focus_style
    assert buf.get(1, 2).style == s.focus_style  # divider styled too


def test_focus_keeps_single_path_through_nested_splits():
    inner = _split()
    outer = HorizontalSplit(TaskList(lambda: [Task("T")]), inner, ratio=0.5, divider=True)
    render(outer, 8, 8)
    outer.focus_at(0, 7)            # deep in the inner (bottom) pane
    assert outer.focused == 1 and inner.focused == 1
    outer.focus_at(0, 0)           # back to the outer top
    assert outer.focused == 0 and inner.focused is None  # inner path cleared


# -- pane-scoped key dispatch ------------------------------------------------
def test_element_on_and_dispatch_key():
    tl = TaskList(lambda: [Task("a")])
    seen = []
    tl.on("x", lambda k: seen.append(k))
    assert tl.dispatch_key("x") is True
    assert tl.dispatch_key("y") is False   # no handler registered
    assert seen == ["x"]


def test_focused_leaf_tracks_focused_pane():
    top = TaskList(lambda: [Task("T")])
    bot = TaskList(lambda: [Task("B")])
    s = HorizontalSplit(top, bot, divider=True)
    assert s.focused_leaf() is None        # nothing focused yet
    s.focus_pane(0)
    assert s.focused_leaf() is top
    s.focus_pane(1)
    assert s.focused_leaf() is bot


def test_focused_leaf_descends_nested_splits():
    leaf = TaskList(lambda: [Task("x")])
    inner = HorizontalSplit(TaskList(lambda: [Task("a")]), leaf, divider=True)
    outer = HorizontalSplit(TaskList(lambda: [Task("t")]), inner, divider=True)
    outer.focus_pane(1)
    inner.focus_pane(1)
    assert outer.focused_leaf() is leaf


def test_keys_reach_only_the_focused_pane():
    from elka import terminal

    top = TaskList(lambda: [Task("T")])
    bot = TaskList(lambda: [Task("B")])
    layout = HorizontalSplit(top, bot, divider=True)
    terminal.attach(layout)
    got = []
    top.on("up", lambda k: got.append("top"))
    bot.on("up", lambda k: got.append("bot"))

    terminal._dispatch_key("up")           # no focus -> neither pane fires
    assert got == []
    layout.focus_pane(0)
    terminal._dispatch_key("up")
    assert got == ["top"]
    layout.focus_pane(1)
    terminal._dispatch_key("up")
    assert got == ["top", "bot"]


if __name__ == "__main__":
    import traceback

    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                passed += 1
            except Exception:
                failed += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
