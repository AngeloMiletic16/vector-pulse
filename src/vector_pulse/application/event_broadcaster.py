import asyncio

from vector_pulse.application.events import AssetEvent


class EventBroadcaster:
    def __init__(
        self,
        queue_max_size: int = 100,
    ) -> None:
        if queue_max_size < 1:
            raise ValueError(
                "Queue max size must be at least 1"
            )

        self._queue_max_size = queue_max_size
        self._subscribers: set[
            asyncio.Queue[AssetEvent]
        ] = set()

    def subscribe(
        self,
    ) -> asyncio.Queue[AssetEvent]:
        queue: asyncio.Queue[AssetEvent] = asyncio.Queue(
            maxsize=self._queue_max_size
        )

        self._subscribers.add(queue)

        return queue

    def unsubscribe(
        self,
        queue: asyncio.Queue[AssetEvent],
    ) -> None:
        self._subscribers.discard(queue)

    async def publish(
        self,
        event: AssetEvent,
    ) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                    queue.task_done()
                except asyncio.QueueEmpty:
                    pass

            queue.put_nowait(event)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)