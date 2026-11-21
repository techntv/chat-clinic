import threading

from clinic.services import background


def test_sync_mode_runs_inline(settings):
    settings.BACKGROUND_SYNC = True
    seen = []
    background.run_in_background(seen.append, 1)
    assert seen == [1]


def test_thread_mode_runs_in_pool(settings):
    settings.BACKGROUND_SYNC = False
    done = threading.Event()
    names = []

    def task():
        names.append(threading.current_thread().name)
        done.set()

    background.run_in_background(task)
    assert done.wait(5)
    assert names[0].startswith("bg")


def test_errors_are_logged_not_raised(settings, caplog):
    settings.BACKGROUND_SYNC = True

    def boom():
        raise RuntimeError("x")

    background.run_in_background(boom)
    assert "background task failed" in caplog.text
