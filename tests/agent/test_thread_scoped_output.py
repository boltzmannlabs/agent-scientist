"""Tests for agent.thread_scoped_output.thread_scoped_silence.

Behaviour contract: a thread inside ``thread_scoped_silence()`` has its
stdout/stderr routed to devnull, while every OTHER thread keeps writing to the
real stream — even concurrently, while the first thread is still inside the
context.  This is the property the old process-global
``contextlib.redirect_stdout(devnull)`` violated (issue #55769 / #55925).
"""

import contextlib
import io
import sys
import threading
import time
from contextvars import copy_context

import agent.thread_scoped_output as thread_output
from agent.thread_scoped_output import thread_scoped_silence


def test_capture_follows_worker_context_without_capturing_other_threads():
    """A late tool worker keeps its output owner after the caller leaves its scope."""
    from agent.thread_scoped_output import context_scoped_output

    original_out, original_err = sys.stdout, sys.stderr
    main, side, other = io.StringIO(), io.StringIO(), io.StringIO()
    entered, release = threading.Event(), threading.Event()
    sys.stdout = sys.stderr = main

    def worker():
        entered.set()
        assert release.wait(10)
        print('side polling')
        print('side diagnostic', file=sys.stderr)
        sys.stdout.writelines(['side downloaded\n'])
        with thread_scoped_silence():
            print('internal suppressed')

    try:
        with context_scoped_output(side):
            ctx = copy_context()
            thread = threading.Thread(target=ctx.run, args=(worker,))
            thread.start()
            assert entered.wait(10)
        print('main stays main')
        with context_scoped_output(other):
            print('different owner')
        release.set()
        thread.join(10)
        assert not thread.is_alive()
        assert side.getvalue() == 'side polling\nside diagnostic\nside downloaded\n'
        assert main.getvalue() == 'main stays main\n'
        assert other.getvalue() == 'different owner\n'
    finally:
        release.set()
        sys.stdout, sys.stderr = original_out, original_err


def _run_with_real_stream(fn):
    """Bind a StringIO as the real stdout, run fn, return what reached it."""
    real_out = io.StringIO()
    orig = sys.stdout
    sys.stdout = real_out
    try:
        fn()
    finally:
        sys.stdout = orig
    return real_out.getvalue()






def test_stderr_is_also_routed_per_thread():
    real_err = io.StringIO()
    orig = sys.stderr
    sys.stderr = real_err
    try:
        with thread_scoped_silence():
            sys.stderr.write("err-dropped\n")
        sys.stderr.write("err-kept\n")
    finally:
        sys.stderr = orig
    out = real_err.getvalue()
    assert "err-dropped" not in out
    assert "err-kept" in out






def test_many_concurrent_silenced_and_loud_threads():
    """Stress: interleaved silenced/loud threads keep their respective fates."""
    start = threading.Event()
    results_lock = threading.Lock()

    def silenced(i):
        start.wait(timeout=2.0)
        with thread_scoped_silence():
            print(f"S{i}")
            time.sleep(0.05)

    def loud(i):
        start.wait(timeout=2.0)
        time.sleep(0.02)
        print(f"L{i}")

    def body():
        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=silenced, args=(i,)))
            threads.append(threading.Thread(target=loud, args=(i,)))
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join(timeout=15.0)
        assert not any(t.is_alive() for t in threads), "straggler thread would truncate captured output"

    captured = _run_with_real_stream(body)
    for i in range(5):
        assert f"S{i}" not in captured, f"silenced S{i} leaked"
        assert f"L{i}" in captured, f"loud L{i} swallowed"


def test_repeated_contexts_never_write_to_a_closed_sink():
    """The installed proxy must survive later silenced workers."""
    original = sys.stdout
    try:
        for _ in range(3):
            with thread_scoped_silence():
                sys.stdout.write("hidden\n")
            sys.stdout.fileno()
    finally:
        sys.stdout = original


def test_temporary_global_redirects_do_not_allocate_new_sinks(monkeypatch):
    """A displaced proxy is temporary, not a reason to leak another FD pair."""
    opened_sinks = []

    def fake_open(*_args, **_kwargs):
        sink = io.StringIO()
        opened_sinks.append(sink)
        return sink

    monkeypatch.setattr(thread_output, "_installed", {})
    monkeypatch.setattr(thread_output, "_sinks", {}, raising=False)
    monkeypatch.setattr(thread_output, "open", fake_open, raising=False)
    original_stdout, original_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
    try:
        with thread_scoped_silence():
            pass
        assert len(opened_sinks) == 2
        original_proxies = dict(thread_output._installed)

        for _ in range(20):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with thread_scoped_silence():
                    print("hidden")

        with thread_scoped_silence():
            pass
        assert len(opened_sinks) == 2
        assert thread_output._installed == original_proxies
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr


def test_silence_survives_redirect_restoring_an_older_proxy(monkeypatch):
    """Silencing is stream-wide, even when a redirect swaps proxy generations."""
    monkeypatch.setattr(thread_output, "_installed", {})
    monkeypatch.setattr(thread_output, "_sinks", {}, raising=False)
    original_stdout, original_stderr = sys.stdout, sys.stderr
    passthrough = io.StringIO()
    sys.stdout = passthrough
    entered = threading.Event()
    release = threading.Event()

    try:
        with thread_scoped_silence():
            pass

        def worker():
            with thread_scoped_silence():
                entered.set()
                assert release.wait(timeout=10)
                print("must-stay-silenced")

        redirected = io.StringIO()
        with contextlib.redirect_stdout(redirected):
            thread = threading.Thread(target=worker)
            thread.start()
            assert entered.wait(timeout=10)

        release.set()
        thread.join(timeout=10)

        assert not thread.is_alive()
        assert "must-stay-silenced" not in passthrough.getvalue()
        assert "must-stay-silenced" not in redirected.getvalue()
    finally:
        release.set()
        sys.stdout, sys.stderr = original_stdout, original_stderr
