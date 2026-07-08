"""SSE endpoint streaming live price ticks — the data source for frontend charts."""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

KEEPALIVE_SECONDS = 15.0


@router.get("/api/stream/prices")
async def stream_prices(request: Request) -> StreamingResponse:
    cache = request.app.state.price_cache
    queue = cache.subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    tick = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                    yield f"data: {tick.model_dump_json()}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            cache.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
