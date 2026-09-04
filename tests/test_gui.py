"""
Tests for autourgos_textinput.TextInputBox.

pynput's GlobalHotKeys is mocked (no real OS-level hotkey registration in
CI). tkinter itself is real -- these tests exercise actual Tk widgets
programmatically (no human interaction, no real hotkey press) since a
display is generally available; skip automatically if not (e.g. headless
Linux CI without a virtual display).

All GUI-driving tests share ONE TextInputBox/Tk() root for the whole module
(module-scoped fixture) instead of one per test. In normal use a program
creates exactly one TextInputBox and runs `.start()` once on its real main
thread for the whole process lifetime -- that's what this suite is actually
verifying. Creating and destroying multiple independent `tkinter.Tk()` roots
across worker threads within one test process (which an earlier version of
this suite did, one per test) triggers a native Tcl/Tk interpreter-teardown
crash unrelated to this package's own logic -- an artifact of that test
shape, not a defect being tested for, so it's avoided here instead of
worked around.
"""

import sys
import threading
import time
import types

import pytest

tkinter = pytest.importorskip("tkinter")

from autourgos_textinput.gui import TextInputBox, TextInputUnavailableError


def _tk_available() -> bool:
    try:
        root = tkinter.Tk()
        root.destroy()
        return True
    except tkinter.TclError:
        return False


pytestmark = pytest.mark.skipif(not _tk_available(), reason="no display available for tkinter")


class FakeGlobalHotKeys:
    """Stand-in for pynput.keyboard.GlobalHotKeys -- never registers a real OS hook."""

    instances = []

    def __init__(self, mapping):
        self.mapping = mapping
        self.started = False
        self.stopped = False
        FakeGlobalHotKeys.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def trigger(self):
        """Test helper: simulate the hotkey firing, exactly like pynput would."""
        list(self.mapping.values())[0]()


@pytest.fixture(scope="module", autouse=True)
def fake_pynput_module():
    fake_keyboard = types.SimpleNamespace(GlobalHotKeys=FakeGlobalHotKeys)
    fake_pynput_module = types.ModuleType("pynput")
    fake_pynput_module.keyboard = fake_keyboard
    sys.modules["pynput"] = fake_pynput_module
    sys.modules["pynput.keyboard"] = fake_keyboard
    yield fake_keyboard
    sys.modules.pop("pynput", None)
    sys.modules.pop("pynput.keyboard", None)


def test_without_pynput_raises_on_start(monkeypatch):
    monkeypatch.setitem(sys.modules, "pynput", None)
    box = TextInputBox()
    assert box._available is False
    with pytest.raises(TextInputUnavailableError):
        box.start()


def test_constructor_defaults():
    box = TextInputBox()
    assert box.title == "Autourgos Input"
    assert box.hotkey == "<ctrl>+<alt>+space"
    assert box._available is True


@pytest.fixture(scope="module")
def running_box():
    """One TextInputBox, started once for the whole module -- matches real usage."""
    box = TextInputBox(hotkey="<ctrl>+<alt>+t", title="Test Box")
    thread = threading.Thread(target=box.start, daemon=True)
    thread.start()
    time.sleep(0.3)  # let Tk create the root and register the fake hotkey
    box._tk_thread_ident = thread.ident  # test-only bookkeeping, see test_on_submit_runs_off_the_tk_thread
    yield box
    box.stop()
    thread.join(timeout=2)


def _hotkey_sim():
    assert len(FakeGlobalHotKeys.instances) == 1
    return FakeGlobalHotKeys.instances[0]


def _open_popup_and_get_entry(box):
    _hotkey_sim().trigger()
    time.sleep(0.3)
    toplevels = [w for w in box._root.winfo_children() if isinstance(w, tkinter.Toplevel) and w.winfo_exists()]
    assert len(toplevels) == 1, f"expected exactly one popup, found {len(toplevels)}"
    win = toplevels[0]
    entry = next(w for w in win.winfo_children() if isinstance(w, tkinter.Entry))
    return win, entry


def test_hotkey_registered_with_configured_combo(running_box):
    assert _hotkey_sim().started is True
    assert "<ctrl>+<alt>+t" in _hotkey_sim().mapping


def test_hotkey_trigger_shows_popup_and_submit_calls_on_submit(running_box):
    received = []
    done = threading.Event()
    running_box.on_submit = lambda text: (received.append(text), done.set())

    win, entry = _open_popup_and_get_entry(running_box)
    assert win.title() == "Test Box"

    entry.insert(0, "hello world")
    entry.event_generate("<Return>")

    assert done.wait(timeout=3), "on_submit was never called"
    assert received == ["hello world"]


def test_escape_cancels_without_calling_on_submit(running_box):
    received = []
    running_box.on_submit = lambda text: received.append(text)

    win, _entry = _open_popup_and_get_entry(running_box)
    win.event_generate("<Escape>")
    time.sleep(0.3)

    remaining = [w for w in running_box._root.winfo_children() if isinstance(w, tkinter.Toplevel) and w.winfo_exists()]
    assert remaining == []
    assert received == []


def test_empty_submit_does_not_call_on_submit(running_box):
    received = []
    running_box.on_submit = lambda text: received.append(text)

    win, entry = _open_popup_and_get_entry(running_box)
    entry.event_generate("<Return>")  # nothing typed
    time.sleep(0.3)

    assert received == []


def test_on_submit_runs_off_the_tk_thread(running_box):
    """A slow on_submit must not block the GUI -- confirms it runs in a worker thread, not the Tk thread."""
    calling_thread_ident = {}
    done = threading.Event()

    def on_submit(text):
        calling_thread_ident["ident"] = threading.get_ident()
        done.set()

    running_box.on_submit = on_submit
    win, entry = _open_popup_and_get_entry(running_box)
    entry.insert(0, "hi")
    entry.event_generate("<Return>")

    assert done.wait(timeout=3)
    assert calling_thread_ident["ident"] != running_box._tk_thread_ident
