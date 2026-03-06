from __future__ import annotations

import asyncio
import contextlib

from source.config.settings import settings
from source.tasks import process_due_jobs


async def run_worker(stop_event: asyncio.Event | None = None) -> None:
    local_stop = stop_event or asyncio.Event()
    while not local_stop.is_set():
        await process_due_jobs()
        try:
            await asyncio.wait_for(local_stop.wait(), timeout=settings.jobs.poll_interval_seconds)
        except TimeoutError:
            continue


def main() -> None:
    stop_event = asyncio.Event()
    try:
        asyncio.run(run_worker(stop_event))
    except KeyboardInterrupt:
        stop_event.set()
        with contextlib.suppress(RuntimeError):
            asyncio.run(process_due_jobs())


if __name__ == '__main__':
    main()
