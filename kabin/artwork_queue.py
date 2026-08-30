from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable


class ArtworkQueue:
    """Bounded, deduplicated background loader for remote artwork."""

    def __init__(self, fetcher: Callable, dispatcher: Callable, max_workers: int = 4):
        self._fetcher = fetcher
        self._dispatcher = dispatcher
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="kabin-artwork",
        )
        self._lock = threading.Lock()
        self._inflight: dict[tuple, list[Callable]] = {}

    def request(self, host: dict, token: str, game_id: str, callback: Callable) -> None:
        key = (
            host.get("name", ""),
            host.get("address", ""),
            host.get("port", 42424),
            host.get("fingerprint", ""),
            game_id,
        )
        with self._lock:
            callbacks = self._inflight.get(key)
            if callbacks is not None:
                callbacks.append(callback)
                return
            self._inflight[key] = [callback]

        future = self._executor.submit(self._fetch, dict(host), token, game_id)
        future.add_done_callback(lambda completed: self._complete(key, completed.result()))

    def _fetch(self, host: dict, token: str, game_id: str):
        try:
            return self._fetcher(host, token, game_id)
        except Exception:
            return None

    def _complete(self, key: tuple, result) -> None:
        with self._lock:
            callbacks = self._inflight.pop(key, [])
        for callback in callbacks:
            self._dispatcher(callback, result)

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

