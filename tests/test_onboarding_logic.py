import pytest
from unittest.mock import patch, MagicMock
from orion import main
from orion import config
from orion.core.model_fallback import get_recommended_model
from orion.ui.onboarding import validate_api_key

@pytest.fixture
def temp_config(tmp_path):
    conf_file = tmp_path / "config.toml"
    with patch("orion.config.CONFIG_FILE", conf_file):
        yield conf_file

def test_is_config_ready_false_if_missing(temp_config):
    assert config.is_config_ready() is False

def test_save_config_creates_file(temp_config):
    config.save_config("openai:gpt-4o", "sk-123")
    assert temp_config.exists()
    content = temp_config.read_text()
    assert 'model_string = "openai:gpt-4o"' in content
    assert 'api_key = "sk-123"' in content
    assert config.is_config_ready() is True

@patch("orion.main.setup_runtime")
@patch("orion.ui.onboarding.run_onboarding")
@patch("orion.config.is_config_ready")
@patch("orion.config.save_config")
def test_cli_entry_triggers_onboarding_if_not_ready(
    mock_save, mock_ready, mock_onboarding, mock_setup, temp_config
):
    mock_ready.return_value = False
    mock_onboarding.return_value = ("openai:gpt-4o", "sk-test", "Alice", "Pref", None)
    mock_save.return_value = True
    
    with patch("orion.main.sys.argv", ["orion"]), \
         patch("orion.main.asyncio.run"):
        main.cli_entry()
    
    mock_onboarding.assert_called_once()
    mock_save.assert_called_once_with("openai:gpt-4o", "sk-test")
    # setup_runtime should be called after onboarding
    mock_setup.assert_called_once()


def test_recommended_model_includes_mistral():
    assert get_recommended_model("mistral") == "mistral:mistral-large-latest"


def test_validate_api_key_supports_mistral():
    response = MagicMock(status_code=200)
    client = MagicMock()
    client.get.return_value = response
    client.__enter__.return_value = client
    client.__exit__.return_value = None

    with patch("orion.ui.onboarding.httpx.Client", return_value=client):
        is_valid, err = validate_api_key("mistral", "mistral-test-key")

    assert is_valid is True
    assert err == ""
    client.get.assert_called_once_with(
        "https://api.mistral.ai/v1/models",
        headers={"Authorization": "Bearer mistral-test-key"},
    )
