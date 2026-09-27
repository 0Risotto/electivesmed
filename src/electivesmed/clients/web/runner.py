"""Background runner: one long job at a time (SQLite single writer, one agent run)."""

from concurrent.futures import ThreadPoolExecutor


class BackgroundRunner:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="electivesmed")

    def submit(self, fn, *args, **kwargs) -> None:
        self._executor.submit(fn, *args, **kwargs)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
