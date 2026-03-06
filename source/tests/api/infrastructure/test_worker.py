import asyncio

from source.tasks.worker import run_worker


async def test_worker_processes_loop_and_stops() -> None:
    stop_event = asyncio.Event()

    async def stop_soon() -> None:
        await asyncio.sleep(0.01)
        stop_event.set()

    await asyncio.gather(run_worker(stop_event), stop_soon())
