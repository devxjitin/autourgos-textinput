# autourgos-textinput

[![Framework: Autourgos](https://img.shields.io/badge/Framework-Autourgos-orange.svg)](https://github.com/devxjitin)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/autourgos-textinput/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](https://github.com/devxjitin/autourgos-textinput/blob/main/LICENSE)
[![Author](https://img.shields.io/badge/Author-Jitin%20Kumar%20Sengar-blue.svg)](https://github.com/devxjitin)

A global-hotkey-triggered Tkinter popup text input box for the Autourgos framework. Press a shortcut **from anywhere** — no window needs focus — and a small input box pops up; whatever's typed gets handed to a callback. Both the shortcut and the popup's title are user-defined; the title defaults to **"Autourgos Input"**.

**Input only, deliberately.** This package captures text and hands it off, full stop — it does not display anything back (no "response" popup). Showing a result belongs in a separate package; don't build that on top of this one.

```python
from autourgos_textinput import TextInputBox

def on_submit(text: str) -> None:
    result = my_agent.invoke(text)
    print(result)  # or log it, forward it, whatever -- your call, not this package's

box = TextInputBox(hotkey="<ctrl>+<alt>+space", title="Autourgos Input", on_submit=on_submit)
box.start()  # blocks -- run from your main thread
# Press Ctrl+Alt+Space anywhere -> type -> Enter -> on_submit(text) fires.
```

---

## Install

```bash
pip install "autourgos-textinput[gui]"
```

`pynput` (for the global hotkey listener) is required only to actually call `TextInputBox.start()`, gated behind the `gui` extra — `import autourgos_textinput` alone never requires it. `tkinter` is Python's own stdlib GUI toolkit — present on most installs; if missing (some minimal Linux builds), that's surfaced as a clear error rather than an import-time crash. Requires Python 3.10+.

---

## Usage

```python
from autourgos_textinput import TextInputBox

def on_submit(text: str) -> None:
    print("You typed:", text)
    # do whatever with it -- call an agent, log it, forward it elsewhere

box = TextInputBox(hotkey="<ctrl>+<alt>+i", title="Autourgos Input", on_submit=on_submit)
box.start()  # blocks -- call from your program's main thread
```

- **Enter** submits (only if non-empty); `on_submit` then runs in its own worker thread, so a slow call inside it (e.g. an agent/LLM call) never freezes the popup.
- **Escape** (or closing the window) cancels without calling `on_submit`.
- `box.stop()` stops the event loop and hotkey listener — safe to call from any thread.

### With autourgos-agent / autourgos-openaichat / autourgos-responses

None of those packages depend on this one (same reasoning as `autourgos-micinput` — no forced dependency on callers who don't need a GUI). Wire them together yourself, exactly like any other `on_submit`. Full, runnable example — a global-hotkey prompt box for an agent with one tool:

```python
"""
A global-hotkey "ask the agent" popup.

Run this, then press Ctrl+Alt+Space from anywhere -- type a question, hit
Enter, and the agent's answer (with tool calls resolved) prints to this
console. Requires:  pip install "autourgos-textinput[gui]" autourgos-agent autourgos-openaichat
"""
import os

from autourgos_agent import Agent, tool
from autourgos_openaichat import OpenAIChatModel
from autourgos_textinput import TextInputBox, TextInputUnavailableError


@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"22C and sunny in {city}"  # replace with a real weather API call


llm = OpenAIChatModel(model="gpt-4o", api_key=os.environ["OPENAI_API_KEY"])
agent = Agent(llm=llm, verbose=False)
agent.add_tools(get_weather)


def on_submit(text: str) -> None:
    # Runs in its own worker thread (see "Usage" above) -- the popup and
    # the rest of your program stay responsive while this is in flight.
    try:
        result = agent.invoke(text)
    except Exception as exc:
        result = f"Error: {exc}"
    print(f"\n[you] {text}\n[agent] {result}\n")
    # Want this shown back in a GUI instead of the console? That's a
    # separate concern -- this package only captures input (see the note
    # at the bottom of this README).


def main() -> None:
    box = TextInputBox(
        hotkey="<ctrl>+<alt>+space",   # user-defined
        title="Ask the Agent",          # user-defined, defaults to "Autourgos Input"
        on_submit=on_submit,
    )
    print(f"Ready -- press {box.hotkey} anywhere to ask the agent something.")
    try:
        box.start()  # blocks; this must be your program's main thread
    except TextInputUnavailableError as exc:
        print(f"Can't start: {exc}")


if __name__ == "__main__":
    main()
```

If you want the result shown back to the user in a GUI instead of the console, that's a separate concern — nothing in this package does it.

### Hotkey syntax

`hotkey` is a [pynput `GlobalHotKeys`](https://pynput.readthedocs.io/en/latest/keyboard.html#global-hotkeys) combo string — angle-bracket modifier names joined with `+`: `"<ctrl>+<alt>+space"`, `"<ctrl>+<shift>+i"`, `"<cmd>+<alt>+k"`, etc. Defaults to `"<ctrl>+<alt>+space"`.

---

## API Reference

### `TextInputBox(*, hotkey="<ctrl>+<alt>+space", title="Autourgos Input", on_submit=None, width=420)`

| Method | Description |
|---|---|
| `start()` | Blocking. Registers the hotkey and runs Tkinter's event loop. Call from your program's real main thread. |
| `stop()` | Stops the event loop and hotkey listener. Safe to call from any thread. |

### Errors (`autourgos_textinput`)

| Name | Raised when |
|---|---|
| `TextInputError` | Base class |
| `TextInputUnavailableError` | `tkinter` and/or `pynput` aren't available |

---

## A note on testing global hotkeys

`pynput.keyboard.GlobalHotKeys` deliberately ignores synthetic/injected key events (`if not injected:` in its own source) — specifically so a hotkey handler that itself sends keystrokes can't re-trigger its own hotkey in a loop. That means the actual "press the shortcut" step **cannot be simulated** by injecting keys programmatically (e.g. via `pynput.Controller`), even for testing — only a genuine physical key press fires it. This package's test suite verifies everything downstream of that (popup creation, focus, typed text, Enter/Escape handling, the worker-thread dispatch) against a real Tkinter GUI with the hotkey *trigger* simulated directly (calling the registered callback, the same call `GlobalHotKeys` itself would make) — the one thing it cannot exercise end-to-end in an automated environment is the OS actually delivering a real keypress, which requires a human at a keyboard.

---

## License

Apache License 2.0, Copyright (c) 2026 Jitin Kumar Sengar
