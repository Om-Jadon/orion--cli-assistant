import struct
import httpx
from config import OLLAMA_API_BASE, EMBED_MODEL, EMBED_DIM


async def embed(text: str) -> list[float]:
    """Generate embeddings for text via Ollama's embeddings API.

    Args:
        text: The text to embed.

    Returns:
        A list of floats truncated to EMBED_DIM.

    Raises:
        httpx.RequestError: If the HTTP request fails.
        KeyError: If the response is missing the 'embedding' field.
    """
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{OLLAMA_API_BASE}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=10
        )
        full_vector = r.json()["embedding"]
        return full_vector[:EMBED_DIM]


def serialize(floats: list[float]) -> bytes:
    """Serialize a list of floats to bytes using struct packing.

    Args:
        floats: A list of floats to serialize.

    Returns:
        Binary representation of the floats.
    """
    return struct.pack(f"{len(floats)}f", *floats)
