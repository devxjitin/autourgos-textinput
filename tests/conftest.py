"""
Works around a known Tcl/Tk + background-thread interpreter-teardown crash:
running a Tk() mainloop on a non-main thread (this package's own test suite
does, deliberately, to drive the GUI without blocking pytest) can leave a
native Tcl async handler that gets torn down by the "wrong" thread during
Python's normal interpreter finalization, printing
"Tcl_AsyncDelete: async handler deleted by the wrong thread" and corrupting
the process exit code even when every test actually passed. This is a
long-standing Tcl/Tk quirk, not specific to this package's logic (the same
class of issue shows up in other GUI-toolkit test suites that drive the
toolkit from a worker thread).

Fix: after pytest has finished reporting results (the `yield` below lets
every other pytest_sessionfinish implementation -- including the terminal
reporter's own summary line -- run first), skip Python's normal
(Tcl-touching) interpreter finalization and exit immediately with pytest's
real exit status instead.
"""
import os
import sys

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_sessionfinish(session, exitstatus):
    yield
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(int(exitstatus))
