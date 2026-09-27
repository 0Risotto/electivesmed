import threading

from electivesmed.clients.web.runner import BackgroundRunner


def test_runner_executes_jobs_and_shuts_down():
    runner = BackgroundRunner()
    results: list = []
    done = threading.Event()

    def job(value):
        results.append(value)
        done.set()

    runner.submit(job, 42)

    assert done.wait(timeout=5)
    runner.shutdown()
    assert results == [42]
