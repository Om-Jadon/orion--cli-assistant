import struct
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_embed_returns_correct_dim():
    """Test that embed() returns a vector of EMBED_DIM length."""
    import numpy as np
    from orion.config import EMBED_DIM

    fake_vector = np.array([0.1] * EMBED_DIM)

    with patch("orion.memory.embeddings._get_model") as mock_get_model:
        mock_model = MagicMock()
        mock_model.embed.return_value = iter([fake_vector])
        mock_get_model.return_value = mock_model

        from orion.memory.embeddings import embed
        result = await embed("test text")

        assert len(result) == EMBED_DIM
        assert isinstance(result, list)
        assert isinstance(result[0], float)


def test_serialize_produces_correct_bytes():
    """Test that serialize() produces correct binary output matching the input floats."""
    from orion.memory.embeddings import serialize

    test_floats = [1.0, 2.0, 3.0]
    serialized = serialize(test_floats)

    # Verify byte length: 3 floats × 4 bytes per float = 12 bytes
    assert len(serialized) == 12

    # Verify unpacking produces the same floats
    unpacked = struct.unpack("3f", serialized)
    assert unpacked == tuple(test_floats)


def test_serialize_empty_list():
    """Test that serialize() handles an empty list."""
    from orion.memory.embeddings import serialize

    serialized = serialize([])
    assert len(serialized) == 0
    assert serialized == b""


def test_serialize_large_vector():
    """Test that serialize() handles a 256-dim vector correctly."""
    from orion.memory.embeddings import serialize
    from orion.config import EMBED_DIM

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
    from orion.memory.embeddings import serialize
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


@pytest.mark.asyncio
async def test_get_model_uses_config_embed_model():
    from orion.memory import embeddings as embeddings_mod

    embeddings_mod._model = None
    try:
        with patch("orion.memory.embeddings.TextEmbedding") as mock_text_embedding:
            fake_model = MagicMock()
            mock_text_embedding.return_value = fake_model

            got = await embeddings_mod._get_model()

        assert got is fake_model
        mock_text_embedding.assert_called_once_with(embeddings_mod.config.EMBED_MODEL)
    finally:
        embeddings_mod._model = None
