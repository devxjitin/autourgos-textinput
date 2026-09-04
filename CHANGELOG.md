# Changelog

## 0.1.3

- Internal: `__version__` resolution moved to `autourgos_core.package_version()` (bumped `autourgos-core>=0.3.0`). No functional change.

## 0.1.2

- Internal: `_load_deps()`'s import-probing logic moved to `autourgos_core.try_import()` (new `autourgos-core>=0.1.0` dependency), and `_require_available()`'s conditional-raise moved to `autourgos_core.require_available()`. No behavior change -- error messages stay identical.

## 0.1.1

- **Removed scope creep: `show_message()` and `run_with_agent()`.** This package was built to only capture input via a hotkey-triggered popup and hand it to a callback -- it should never have grown a second "response" popup or auto-display logic. Neither was asked for; corrected. `TextInputBox` now only ever shows the one input popup; displaying a result is left entirely to the caller (or a separate, not-yet-built output package). `.post()` was internal-only anyway (renamed `_post()`) since it existed solely to support the removed response popup.
- No other behavior changed. 7 tests (was 8 -- the `run_with_agent`/response-popup test removed along with the code it tested; a new `test_on_submit_runs_off_the_tk_thread` added to keep coverage of the worker-thread dispatch that test also happened to exercise).

## 0.1.0

- Initial release: `TextInputBox` -- a global-hotkey-triggered Tkinter popup text input. Registers a `pynput.keyboard.GlobalHotKeys` combo (works from anywhere, no window focus needed), pops up a small input box (`title`, default "Autourgos Input"), and calls `on_submit(text)` in a worker thread on Enter (non-empty only) -- keeps the GUI responsive during a slow agent/LLM call. Escape or closing the window cancels.
- Live-verified: real Tkinter widget interaction (popup creation/focus/typed-text/Enter/Escape) all confirmed against an actual Tk GUI, hotkey trigger simulated by calling the same callback `GlobalHotKeys` itself would call. Attempted a fully non-simulated test using `pynput.Controller` to inject the real key combo -- discovered `GlobalHotKeys` deliberately ignores injected/synthetic key events by design (`if not injected:` in its own source, to prevent a hotkey handler's own synthesized keystrokes from re-triggering it), so the actual physical-keypress trigger step is fundamentally untestable by self-injection; documented in the README rather than worked around.
- A Tcl/Tk + background-thread interpreter-teardown quirk (`Tcl_AsyncDelete: async handler deleted by the wrong thread`, corrupting the test process's exit code even when every test passed) was found and worked around in the test suite's own `conftest.py` -- not a defect in the package itself, an artifact of driving a Tk mainloop from a non-main thread within a single test process.
