import struct
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_embed_truncates_to_dim():
    """Test that embed() truncates a 768-dim vector to EMBED_DIM (256)."""
    # Create a mock full vector of 768 dimensions (typical for nomic-embed-text)
    full_vector = list(range(768))  # [0, 1, 2, ..., 767]

    # Mock the httpx.AsyncClient.post method
    mock_response = MagicMock()
    mock_response.json.return_value = {"embedding": full_vector}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        from memory.embeddings import embed
        from config import EMBED_DIM

        result = await embed("test text")

        # Verify the result is truncated to EMBED_DIM
        assert len(result) == EMBED_DIM
        # Verify it matches the first EMBED_DIM elements
        assert result == full_vector[:EMBED_DIM]

        # Verify the HTTP call was made correctly
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "api/embeddings" in call_args.args[0]
        assert call_args.kwargs["json"]["prompt"] == "test text"


@pytest.mark.asyncio
async def test_embed_passes_model_and_prompt():
    """Test that embed() passes the correct model and prompt to Ollama."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        from memory.embeddings import embed
        from config import EMBED_MODEL

        await embed("hello world")

        # Verify the API call
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["model"] == EMBED_MODEL
        assert call_kwargs["json"]["prompt"] == "hello world"
        assert call_kwargs["timeout"] == 10


def test_serialize_produces_correct_bytes():
    """Test that serialize() produces correct binary output matching the input floats."""
    from memory.embeddings import serialize

    test_floats = [1.0, 2.0, 3.0]
    serialized = serialize(test_floats)

    # Verify byte length: 3 floats × 4 bytes per float = 12 bytes
    assert len(serialized) == 12

    # Verify unpacking produces the same floats
    unpacked = struct.unpack("3f", serialized)
    assert unpacked == tuple(test_floats)


def test_serialize_empty_list():
    """Test that serialize() handles an empty list."""
    from memory.embeddings import serialize

    serialized = serialize([])
    assert len(serialized) == 0
    assert serialized == b""


def test_serialize_large_vector():
    """Test that serialize() handles a 256-dim vector correctly."""
    from memory.embeddings import serialize
    from config import EMBED_DIM

    # Create a vector of EMBED_DIM floats
    large_vector = [float(i) for i in range(EMBED_DIM)]
    serialized = serialize(large_vector)

    # Verify byte length: 256 × 4 = 1024 bytes
    assert len(serialized) == EMBED_DIM * 4

    # Verify unpacking produces the same values
    unpacked = struct.unpack(f"{EMBED_DIM}f", serialized)
    assert list(unpacked) == large_vector


def test_serialize_roundtrip():
    """Test that serialization and deserialization are symmetric."""
    from memory.embeddings import serialize
    import struct

    original = [0.123, -45.678, 999.999, 0.0, -0.0]
    serialized = serialize(original)
    deserialized = list(struct.unpack(f"{len(original)}f", serialized))

    # Use approximate equality due to floating-point precision
    # 32-bit floats have limited precision; relative tolerance handles both small and large values
    for orig, deser in zip(original, deserialized):
        # Use relative tolerance for larger numbers and absolute for values near zero
        if orig == 0.0:
            assert deser == 0.0
        else:
            rel_error = abs(orig - deser) / abs(orig)
            assert rel_error < 1e-4
