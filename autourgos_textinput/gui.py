"""
TextInputBox -- a global-hotkey-triggered Tkinter popup for autourgos-textinput.

Architecture:
  - A hidden Tk root runs `mainloop()` on the thread that calls `.start()`
    (must be the program's real main thread -- Tkinter is not safe to drive
    from a background thread on most platforms).
  - `pynput.keyboard.GlobalHotKeys` runs its own background listener thread
    and fires a callback when the configured combo is pressed, even while
    no window has focus.
  - The hotkey callback never touches Tkinter directly (cross-thread Tk
    calls are unsafe) -- it posts a callable onto a `queue.Queue`, which the
    Tk root drains on a `root.after()` timer running on the Tk thread
    itself. This is the standard safe pattern for driving Tkinter from
    another thread.
  - Submitting the popup's text runs `on_submit(text)` in its own worker
    thread, so a slow call inside it (e.g. an agent/LLM call) doesn't freeze
    the GUI. This package is input-only -- it hands text to `on_submit` and
    stops there; displaying a result is a separate concern, out of scope
    here (see the sibling output package instead of adding a second popup
    to this one).
"""

from __future__ import annotations

import queue
import threading
from typing import Any, Callable, Optional, Tuple

from autourgos_core import require_available, try_import

_DEFAULT_HOTKEY = "<ctrl>+<alt>+space"
_DEFAULT_TITLE = "Autourgos Input"


class TextInputError(Exception):
    """Base error for autourgos-textinput."""


class TextInputUnavailableError(TextInputError):
    """Raised when `tkinter` and/or `pynput` aren't available."""


def _load_deps() -> Tuple[bool, Any, Any, Optional[str]]:
    """Try to import tkinter and pynput.keyboard. Returns (available, tkinter module, pynput.keyboard module, error)."""
    tk_available, tk_modules, tk_error = try_import("tkinter")
    if not tk_available:
        return False, None, None, f"tkinter is not available: {tk_error}"
    kb_available, kb_modules, kb_error = try_import("pynput.keyboard")
    if not kb_available:
        return False, None, None, (
            "The 'pynput' package is required for the global hotkey listener "
            f"(pip install autourgos-textinput[gui]). Import error: {kb_error}"
        )
    return True, tk_modules["tkinter"], kb_modules["pynput.keyboard"], None


class TextInputBox:
    """
    A global-hotkey-triggered popup text input box.

    Usage::

        def on_submit(text: str) -> None:
            print("You typed:", text)

        box = TextInputBox(hotkey="<ctrl>+<alt>+space", title="Autourgos Input", on_submit=on_submit)
        box.start()  # blocks -- call from your program's main thread

    Press the hotkey from anywhere (no window needs focus) to pop up the
    input box. Enter submits, Escape (or closing the window) cancels
    without calling `on_submit`.
    """

    def __init__(
        self,
        *,
        hotkey: str = _DEFAULT_HOTKEY,
        title: str = _DEFAULT_TITLE,
        on_submit: Optional[Callable[[str], None]] = None,
        width: int = 420,
    ) -> None:
        """
        hotkey: a pynput GlobalHotKeys combo string, e.g. "<ctrl>+<alt>+space"
            or "<ctrl>+<shift>+i". See pynput's docs for the full syntax
            (angle-bracket modifier names: <ctrl>, <alt>, <shift>, <cmd>).
        title: window title AND the label shown above the input field.
            Defaults to "Autourgos Input".
        on_submit: called with the typed text (stripped) when the user
            presses Enter with non-empty input. Runs in its own worker
            thread, not the Tk thread -- this package does not display
            whatever `on_submit` returns; that's a separate concern.
        width: popup width in pixels.
        """
        self._available, self._tkinter, self._pynput_keyboard, self._import_error = _load_deps()
        self.hotkey = hotkey
        self.title = title
        self.on_submit = on_submit
        self.width = width

        self._root: Any = None
        self._queue: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self._listener: Any = None
        self._running = False

    def _require_available(self) -> None:
        require_available(
            self._available,
            f"autourgos-textinput is unavailable. Detail: {self._import_error}",
            TextInputUnavailableError,
        )

    def _post(self, fn: Callable[[], None]) -> None:
        """Schedule `fn` to run on the Tk thread (internal -- used by the hotkey callback and stop())."""
        self._queue.put(fn)

    def start(self) -> None:
        """
        Register the global hotkey and run Tkinter's event loop. Blocks
        until `.stop()` is called (typically from within a callback) or the
        process exits. Call this from your program's actual main thread.
        """
        self._require_available()
        tkinter = self._tkinter

        self._root = tkinter.Tk()
        self._root.withdraw()  # the root itself is never shown -- only popups are

        self._listener = self._pynput_keyboard.GlobalHotKeys({self.hotkey: lambda: self._post(self._show_input_popup)})
        self._listener.start()

        self._running = True
        self._root.after(50, self._poll_queue)
        try:
            self._root.mainloop()
        finally:
            if self._listener is not None:
                self._listener.stop()

    def stop(self) -> None:
        """Stop the event loop and hotkey listener. Safe to call from any thread."""
        self._running = False
        if self._root is not None:
            self._post(self._shutdown)

    def _shutdown(self) -> None:
        # destroy() (not just quit()) tears down the Tcl widget hierarchy
        # immediately and lets mainloop() return on its own -- quit() alone
        # can leave a stale after() callback pending against this root,
        # which then misfires once another Tk() root exists later in the
        # same process (observed running this package's own test suite,
        # which creates a fresh TextInputBox/Tk() per test).
        if self._root is not None:
            self._root.destroy()

    def _poll_queue(self) -> None:
        try:
            while True:
                fn = self._queue.get_nowait()
                fn()
        except queue.Empty:
            pass
        if self._running and self._root is not None:
            self._root.after(50, self._poll_queue)

    # ── popups (always called on the Tk thread) ─────────────────────────────

    def _show_input_popup(self) -> None:
        tkinter = self._tkinter
        win = tkinter.Toplevel(self._root)
        win.title(self.title)
        win.attributes("-topmost", True)
        win.resizable(False, False)

        label = tkinter.Label(win, text=self.title, font=("Segoe UI", 10, "bold"))
        label.pack(padx=16, pady=(14, 4))

        entry_var = tkinter.StringVar()
        entry = tkinter.Entry(win, textvariable=entry_var, width=44, font=("Segoe UI", 11))
        entry.pack(padx=16, pady=(0, 14))

        height = 92
        win.update_idletasks()
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = (screen_w - self.width) // 2
        y = (screen_h - height) // 3
        win.geometry(f"{self.width}x{height}+{x}+{y}")

        def submit(_event: Any = None) -> None:
            text = entry_var.get().strip()
            win.destroy()
            if text and self.on_submit is not None:
                threading.Thread(target=self.on_submit, args=(text,), daemon=True).start()

        def cancel(_event: Any = None) -> None:
            win.destroy()

        entry.bind("<Return>", submit)
        win.bind("<Escape>", cancel)
        win.protocol("WM_DELETE_WINDOW", cancel)

        win.grab_set()
        entry.focus_force()
