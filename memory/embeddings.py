import struct
from fastembed import TextEmbedding
from config import EMBED_DIM

_model: TextEmbedding | None = None

def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding("BAAI/bge-small-en-v1.5")
    return _model


async def embed(text: str) -> list[float]:
    model = _get_model()
    vector = next(model.embed([text]))
    return vector[:EMBED_DIM].tolist()


def serialize(floats: list[float]) -> bytes:
    return struct.pack(f"{len(floats)}f", *floats)
