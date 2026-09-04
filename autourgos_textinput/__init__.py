"""
autourgos-textinput
=====================
A global-hotkey-triggered Tkinter popup text input box for the Autourgos
framework. Press a user-defined shortcut from anywhere -- no window needs
focus -- and a small input box pops up (title also user-defined, default
"Autourgos Input"); whatever's typed gets handed to a callback.

Input only, deliberately: this package captures text and hands it off, full
stop. Displaying a result back to the user (e.g. an agent's reply) is a
separate concern and belongs in a separate package -- do not build that on
top of this one.

Zero dependency to import; `pynput` (for the global hotkey listener) is
required only to actually call `TextInputBox.start()`
(`pip install autourgos-textinput[gui]`). `tkinter` is Python's own stdlib
GUI toolkit -- present on most installs, but some minimal Linux builds omit
it; that's also handled as a clear error rather than an import-time crash.

Quick start::

    from autourgos_textinput import TextInputBox

    def on_submit(text: str) -> None:
        print("You typed:", text)
        # do whatever with it -- call an agent, log it, forward it elsewhere

    box = TextInputBox(hotkey="<ctrl>+<alt>+space", title="Autourgos Input", on_submit=on_submit)
    box.start()  # blocks -- call from your program's main thread
"""

from .gui import TextInputBox, TextInputError, TextInputUnavailableError

try:
    from importlib.metadata import version as _v
    __version__ = _v("autourgos-textinput")
except Exception:
    __version__ = "0.1.0"

__all__ = [
    "TextInputBox",
    "TextInputError",
    "TextInputUnavailableError",
]
