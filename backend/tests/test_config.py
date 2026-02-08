import os
import importlib

import pytest


def test_config_requires_secret_key():
    """Config module raises RuntimeError when SECRET_KEY is not set."""
    env_backup = os.environ.pop("SECRET_KEY", None)
    try:
        # Remove cached module so it re-executes on import
        import sys
        sys.modules.pop("backend.app.config", None)

        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            import backend.app.config  # noqa: F401
    finally:
        if env_backup is not None:
            os.environ["SECRET_KEY"] = env_backup


def test_config_loads_secret_key_from_env():
    """Config module loads SECRET_KEY from environment variable."""
    import sys
    sys.modules.pop("backend.app.config", None)

    os.environ["SECRET_KEY"] = "test-secret-key-12345"
    try:
        import backend.app.config as config
        importlib.reload(config)
        assert config.SECRET_KEY == "test-secret-key-12345"
    finally:
        pass  # Leave SECRET_KEY set for other tests


def test_config_has_token_expiry_defaults():
    """Config module has sensible default values for token expiration."""
    os.environ.setdefault("SECRET_KEY", "test-secret")
    import sys
    sys.modules.pop("backend.app.config", None)

    import backend.app.config as config
    importlib.reload(config)

    assert config.ALGORITHM == "HS256"
    assert config.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert config.REFRESH_TOKEN_EXPIRE_DAYS == 7


def test_config_cors_origins_default():
    """Config module defaults CORS_ORIGINS to localhost:5173."""
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.pop("CORS_ORIGINS", None)
    import sys
    sys.modules.pop("backend.app.config", None)

    import backend.app.config as config
    importlib.reload(config)

    assert "http://localhost:5173" in config.CORS_ORIGINS


def test_config_cors_origins_from_env():
    """Config module parses comma-separated CORS_ORIGINS."""
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ["CORS_ORIGINS"] = "http://localhost:5173,http://example.com"
    import sys
    sys.modules.pop("backend.app.config", None)

    import backend.app.config as config
    importlib.reload(config)

    assert config.CORS_ORIGINS == ["http://localhost:5173", "http://example.com"]
    os.environ.pop("CORS_ORIGINS", None)


def test_config_refresh_cookie_path_default():
    """Config module defaults REFRESH_COOKIE_PATH to /auth/refresh."""
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.pop("REFRESH_COOKIE_PATH", None)
    import sys
    sys.modules.pop("backend.app.config", None)

    import backend.app.config as config
    importlib.reload(config)

    assert config.REFRESH_COOKIE_PATH == "/auth/refresh"


def test_config_refresh_cookie_path_from_env():
    """Config module reads REFRESH_COOKIE_PATH from environment."""
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ["REFRESH_COOKIE_PATH"] = "/api/auth/refresh"
    import sys
    sys.modules.pop("backend.app.config", None)

    import backend.app.config as config
    importlib.reload(config)

    assert config.REFRESH_COOKIE_PATH == "/api/auth/refresh"
    os.environ.pop("REFRESH_COOKIE_PATH", None)
