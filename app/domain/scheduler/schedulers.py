import asyncio
from typing import Callable, Any
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(
        self,
        callback: Callable,
        callback_kwargs: list[dict[str, Any]],
        frequency: timedelta,
    ):
        if not asyncio.iscoroutinefunction(callback):
            raise ValueError("Callback must be an asynchronous function")

        self.callback = callback
        self.callback_kwargs = callback_kwargs
        self.frequency = frequency
        self.is_stopped = False
        self._task = None

    async def sleep(self, duration: timedelta):
        time_target = asyncio.get_event_loop().time() + duration.total_seconds()
        logger.info(
            f"Scheduler sleeping for {duration.total_seconds()} seconds, until {time_target}"
        )
        while asyncio.get_event_loop().time() < time_target:
            if self.is_stopped:
                break
            await asyncio.sleep(1)

    async def _run_loop(self):
        while not self.is_stopped:
            start = asyncio.get_event_loop().time()
            tasks = []
            for callback_kwarg in self.callback_kwargs:
                tasks.append(asyncio.create_task(self.callback(**callback_kwarg)))

            if tasks:
                await asyncio.gather(*tasks)
            elapsed = asyncio.get_event_loop().time() - start
            sleep_time = self.frequency.total_seconds() - elapsed
            if sleep_time > 0:
                await self.sleep(timedelta(seconds=sleep_time))

    async def start(self):
        self._task = asyncio.create_task(self._run_loop())

    def stop(self, force: bool = False):
        self.is_stopped = True
        if force and self._task:
            self._task.cancel()

    def run_forever(self):
        """Run the scheduler in a blocking manner."""
        try:
            asyncio.run(self._run_loop())
        except KeyboardInterrupt:
            self.stop(force=True)
