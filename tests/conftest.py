import pytest
from unittest.mock import MagicMock
from orion import main

@pytest.fixture(autouse=True)
def initialize_main_state():
    """Ensure main.state and main.conn are initialized for tests."""
    if main.state is None:
        main.state = MagicMock()
        # Ensure it has necessary attributes
        main.state.session_id = "test-session"
        main.state.agent = MagicMock()
        
    if main.conn is None:
        main.conn = MagicMock()
