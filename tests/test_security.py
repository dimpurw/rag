import asyncio

import pytest
from fastapi import HTTPException

from app.core.security import verify_api_key


class _FakeSettings:
    api_key = "secret-123"


class _FakeSettingsNoAuth:
    api_key = None


def test_verify_api_key_valid(monkeypatch):
    monkeypatch.setattr("app.core.security.get_settings", lambda: _FakeSettings())
    asyncio.run(verify_api_key(x_api_key="secret-123"))  # tidak boleh raise


def test_verify_api_key_invalid_raises_401(monkeypatch):
    monkeypatch.setattr("app.core.security.get_settings", lambda: _FakeSettings())
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(verify_api_key(x_api_key="salah"))
    assert exc_info.value.status_code == 401


def test_verify_api_key_missing_header_raises_401(monkeypatch):
    monkeypatch.setattr("app.core.security.get_settings", lambda: _FakeSettings())
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(verify_api_key(x_api_key=None))
    assert exc_info.value.status_code == 401


def test_verify_api_key_disabled_when_not_configured(monkeypatch):
    monkeypatch.setattr("app.core.security.get_settings", lambda: _FakeSettingsNoAuth())
    asyncio.run(verify_api_key(x_api_key=None))  # tidak boleh raise, auth nonaktif
