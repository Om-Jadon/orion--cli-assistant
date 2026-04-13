import os
import pytest
import sqlite3
from unittest.mock import patch, AsyncMock
from orion import main
from orion import config
from orion.memory.store import get_recent_turns

@pytest.fixture
def integration_runtime(tmp_path, monkeypatch):
    """Provides a fully initialized, isolated Orion runtime for integration testing."""
    test_dir = tmp_path / ".orion"
    db_path = test_dir / "orion.db"
    
    # Patch all the environment/config stuff to avoid affecting the user's system
    monkeypatch.setattr(config, "ORION_DIR", test_dir)
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setattr(config, "MODEL_STRING", "openai:gpt-4o")
    monkeypatch.setattr(config, "PROVIDER", "openai")

    # Call setup_runtime to initialize DB, memory, states, etc.
    main.setup_runtime()
    
    yield
    
    # Teardown
    if main.conn:
        main.conn.close()


@pytest.mark.asyncio
async def test_full_turn_pipeline(integration_runtime):
    """
    Test the full interactive turn pipeline:
    User input -> context build -> agent streaming -> response save.
    """
    from pydantic_ai.models.test import TestModel
    
    # Inject a TestModel into the global agent
    # We set a custom response that the TestModel will yield, and disable automatic tool calls.
    test_model = TestModel(custom_output_text="I am a test response.", call_tools=[])
    main.state.agent.model = test_model
    
    user_query_1 = "Hello! This is turn 1."
    
    # We patch stdout/print to keep the test output clean
    from unittest.mock import MagicMock
    with patch("orion.main.print_user"), \
         patch("orion.main.print_separator"), \
         patch("orion.core.streaming.console.print"), \
         patch("orion.core.streaming.spinner.start", new=MagicMock()), \
         patch("orion.core.streaming.spinner.stop", new=AsyncMock()):
        
        # 1. First Turn
        await main.run_once(user_query_1, mode="interactive")
        
        # Verify the DB has the saved turns
        turns = get_recent_turns(main.conn, main.state.session_id, max_tokens=1000)
        assert "USER: Hello! This is turn 1." in turns
        assert "ASSISTANT: I am a test response." in turns

        # 2. Second Turn
        user_query_2 = "This is turn 2."
        test_model.custom_output_text = "I remember turn 1!"
        
        await main.run_once(user_query_2, mode="interactive")
        
        # Verify both turns are persisted correctly
        turns = get_recent_turns(main.conn, main.state.session_id, max_tokens=1000)
        assert "USER: Hello! This is turn 1." in turns
        assert "ASSISTANT: I am a test response." in turns
        assert "USER: This is turn 2." in turns
        assert "ASSISTANT: I remember turn 1!" in turns
