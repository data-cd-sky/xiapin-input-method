#!/usr/bin/python3
import sys
import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus


def iterate_until(predicate, attempts=100):
    for _ in range(attempts):
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        if predicate():
            return True
        GLib.usleep(50_000)
    return False


IBus.init()
bus = IBus.Bus.new()
if not bus.is_connected():
    raise SystemExit("IBus test bus is unavailable")
context = bus.create_input_context("xiapin-integration-test")
commits = []
preedits = []
lookup_tables = []
context.connect("commit-text", lambda _context, text: commits.append(text.get_text()))
context.connect(
    "update-preedit-text",
    lambda _context, text, cursor, visible: preedits.append(
        (text.get_text(), cursor, visible)
    ),
)
context.connect(
    "update-lookup-table",
    lambda _context, table, visible: lookup_tables.append(
        (
            table.get_orientation(),
            table.get_page_size(),
            visible,
            table.get_number_of_candidates(),
        )
    ),
)
context.set_capabilities(
    int(
        IBus.Capabilite.PREEDIT_TEXT
        | IBus.Capabilite.LOOKUP_TABLE
        | IBus.Capabilite.FOCUS
    )
)
context.set_engine("xiapin")
context.focus_in()


def key(keyval, state=0, handled=True):
    result = context.process_key_event(keyval, 0, int(state))
    if handled and not result:
        raise SystemExit(f"Xiapin rejected key {keyval}")
    if not handled and result:
        raise SystemExit(f"Xiapin swallowed key {keyval}")
    return result


def type_text(text):
    for character in text:
        key(ord(character))


def committed_after(action):
    before = len(commits)
    action()
    if not iterate_until(lambda: len(commits) > before):
        raise SystemExit("Xiapin did not emit a commit")
    return commits[-1]


# An idle input method must pass ordinary editing, navigation, paging and
# selection keys back to the application. Chinese punctuation is intentionally
# handled below; other ordinary punctuation still belongs to the application.
for idle_key in (
    IBus.KEY_space,
    IBus.KEY_BackSpace,
    IBus.KEY_Delete,
    IBus.KEY_Left,
    IBus.KEY_Right,
    IBus.KEY_Home,
    IBus.KEY_End,
    IBus.KEY_Up,
    IBus.KEY_Down,
    IBus.KEY_Page_Up,
    IBus.KEY_Page_Down,
    IBus.KEY_Return,
    IBus.KEY_1,
    IBus.KEY_9,
    IBus.KEY_minus,
    IBus.KEY_equal,
    IBus.KEY_grave,
):
    key(idle_key, handled=False)

# Chinese mode emits Chinese punctuation both when idle and after a pinyin
# composition. Shifted punctuation must not be mistaken for the Shift toggle.
if committed_after(lambda: key(IBus.KEY_comma)) != "，":
    raise SystemExit(f"Chinese comma produced {commits[-1]!r}")
if committed_after(lambda: key(IBus.KEY_period)) != "。":
    raise SystemExit(f"Chinese period produced {commits[-1]!r}")
if committed_after(
    lambda: key(IBus.KEY_question, IBus.ModifierType.SHIFT_MASK)
) != "？":
    raise SystemExit(f"Chinese question mark produced {commits[-1]!r}")
type_text("nihao")
if committed_after(lambda: key(IBus.KEY_comma)) != "你好，":
    raise SystemExit(f"pinyin plus Chinese comma produced {commits[-1]!r}")

if not iterate_until(lambda: context.process_key_event(IBus.KEY_n, 0, 0)):
    raise SystemExit("Xiapin engine instance did not accept the first key")
if not iterate_until(lambda: bool(lookup_tables)):
    raise SystemExit("Xiapin did not emit a lookup table")
if lookup_tables[-1][:3] != (IBus.Orientation.HORIZONTAL, 9, True):
    raise SystemExit(
        f"expected a visible horizontal nine-item lookup table, received "
        f"{lookup_tables[-1]!r}"
    )
type_text("ihao")
if committed_after(lambda: key(IBus.KEY_space)) != "你好":
    raise SystemExit(f"expected 你好, received {commits[-1]!r}")
if not any(item[0] == "ni hao" and item[2] for item in preedits):
    raise SystemExit(f"expected preedit was not emitted: {preedits!r}")

# Middle editing: nihao -> niao -> nio -> niho, then Enter commits raw pinyin.
type_text("nihao")
key(IBus.KEY_Left)
key(IBus.KEY_Left)
key(IBus.KEY_BackSpace)
key(IBus.KEY_Delete)
type_text("h")
if committed_after(lambda: key(IBus.KEY_Return)) != "niho":
    raise SystemExit(f"middle editing produced {commits[-1]!r}")

# An apostrophe controls the pinyin boundary and numeric keys select candidates.
type_text("xi'an")
if committed_after(lambda: key(IBus.KEY_1)) != "西安":
    raise SystemExit(f"apostrophe segmentation produced {commits[-1]!r}")
type_text("nihao")
if committed_after(lambda: key(IBus.KEY_1)) != "你好":
    raise SystemExit(f"numeric selection produced {commits[-1]!r}")

# Esc cancels composition without committing; Page Down exposes later candidates.
before = len(commits)
type_text("nihao")
key(IBus.KEY_Escape)
iterate_until(lambda: False, attempts=2)
if len(commits) != before:
    raise SystemExit("Escape committed text")
type_text("shi")
key(IBus.KEY_Page_Down)
later = committed_after(lambda: key(IBus.KEY_1))
if not later or later.isascii():
    raise SystemExit(f"second-page candidate is invalid: {later!r}")

# Selecting to an embedded cursor keeps the suffix, then completes the sentence.
type_text("nihaoma")
key(IBus.KEY_Home)
for _ in range(5):
    key(IBus.KEY_Right)
before = len(commits)
key(IBus.KEY_1)
iterate_until(lambda: False, attempts=2)
if len(commits) != before:
    raise SystemExit("partial candidate selection committed too early")
sentence = committed_after(lambda: key(IBus.KEY_space))
if sentence != "你好吗":
    raise SystemExit(f"partial candidate selection produced {sentence!r}")

# The native core test verifies the exact candidate text and index. Here the
# real IBus path verifies that the ninth key selects that same first-page item.
# Startup already began loading the index off-thread before this client exists.
type_text("xiaolian")
if lookup_tables[-1][3] < 9:
    raise SystemExit("xiaolian has fewer than nine lookup-table candidates")
if committed_after(lambda: key(IBus.KEY_9)) != "😀":
    raise SystemExit(f"Emoji selection produced {commits[-1]!r}")

# A previously selected Chinese segment must remain when Emoji completes the
# remaining pinyin composition.
type_text("nihaoxiaolian")
key(IBus.KEY_Home)
for _ in range(5):
    key(IBus.KEY_Right)
before = len(commits)
key(IBus.KEY_1)
iterate_until(lambda: False, attempts=2)
if len(commits) != before:
    raise SystemExit("Emoji prefix fixture committed before the final choice")
if committed_after(lambda: key(IBus.KEY_9)) != "你好😀":
    raise SystemExit(f"Emoji selection lost its Chinese prefix: {commits[-1]!r}")

# Both supported toggles must pass ordinary letters through while in English.
key(IBus.KEY_space, IBus.ModifierType.CONTROL_MASK)
key(IBus.KEY_a, handled=False)
key(IBus.KEY_space, IBus.ModifierType.CONTROL_MASK)
key(IBus.KEY_Shift_L, handled=False)
key(
    IBus.KEY_Shift_L,
    IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.RELEASE_MASK,
    handled=False,
)
key(IBus.KEY_a, handled=False)
key(IBus.KEY_comma, handled=False)
key(IBus.KEY_period, handled=False)
key(IBus.KEY_Shift_L, handled=False)
key(
    IBus.KEY_Shift_L,
    IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.RELEASE_MASK,
    handled=False,
)

# Modified Shift must be passed back to the application, not inserted as
# lowercase pinyin or interpreted as the standalone mode toggle.
before = len(preedits)
key(IBus.KEY_Shift_L, handled=False)
key(IBus.KEY_A, IBus.ModifierType.SHIFT_MASK, handled=False)
key(
    IBus.KEY_Shift_L,
    IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.RELEASE_MASK,
    handled=False,
)
iterate_until(lambda: False, attempts=2)
if any(item[0] for item in preedits[before:]):
    raise SystemExit("Shift+A leaked into the pinyin preedit")
context.focus_out()
print(
    "xiapin-ibus-integration-ok idle-passthrough=1 idle-space=1 commit=你好 edit=1 apostrophe=1 number=1 "
    "paging=1 partial=1 escape=1 enter=1 shift=1 ctrl-space=1 modified-shift=1 "
    "chinese-punctuation=，。 english-punctuation=,. "
    "horizontal=1 page-size=9 emoji=😀 emoji-prefix=你好😀"
)
