import asyncio
import struct
from fastembed import TextEmbedding
from config import EMBED_DIM, EMBED_MODEL

_model: TextEmbedding | None = None
_model_lock = asyncio.Lock()

async def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        async with _model_lock:
            if _model is None:
                _model = await asyncio.to_thread(TextEmbedding, EMBED_MODEL)
    return _model


async def embed(text: str) -> list[float]:
    model = await _get_model()
    vector = await asyncio.to_thread(lambda: next(model.embed([text])))
    return vector[:EMBED_DIM].tolist()


def serialize(floats: list[float]) -> bytes:
    return struct.pack(f"{len(floats)}f", *floats)
