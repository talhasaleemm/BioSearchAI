import pytest
import importlib
import app.main

@pytest.mark.parametrize("invalid_cors", [
    "   ,  ,, ",  # Whitespace and commas only
    "",            # Exact empty string
])
def test_cors_empty_config_fails_to_start(monkeypatch, invalid_cors):
    """
    Test that setting CORS_ALLOWED_ORIGINS to an empty or whitespace-only string
    causes the application to fail fast on startup with a RuntimeError.
    """
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", invalid_cors)
    
    import app.core.config
    app.core.config.get_settings.cache_clear()
    
    with pytest.raises(RuntimeError) as exc_info:
        importlib.reload(app.main)
        
    assert "CORS_ALLOWED_ORIGINS cannot be empty" in str(exc_info.value)
    
    # Cleanup
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    app.core.config.get_settings.cache_clear()
    importlib.reload(app.main)

def test_cors_missing_config_uses_default(monkeypatch):
    """
    Test that completely omitting CORS_ALLOWED_ORIGINS from the environment
    does NOT fail closed, but instead uses the hardcoded pydantic default
    (which is currently "http://localhost:3000").
    """
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    
    import app.core.config
    app.core.config.get_settings.cache_clear()
    
    # Should NOT raise RuntimeError, should reload successfully
    importlib.reload(app.main)
    
    # Validate the default was applied correctly
    settings = app.core.config.get_settings()
    assert settings.CORS_ALLOWED_ORIGINS == "http://localhost:3000"
    
    # Cleanup
    app.core.config.get_settings.cache_clear()
    importlib.reload(app.main)
