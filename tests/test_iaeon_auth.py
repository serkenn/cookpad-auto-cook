"""Tests for iAEON authentication."""

import pytest

from cookpad.fridge.iaeon.auth import IAEONAuthenticator, IAEONSession
from cookpad.fridge.iaeon.otp import ManualOTPHandler, OTPHandler


class MockOTPHandler(OTPHandler):
    """Mock OTP handler that returns a fixed code."""

    def __init__(self, code: str = "123456"):
        self._code = code

    async def get_otp_code(self, phone: str) -> str:
        return self._code


def test_iaeon_session_dataclass():
    """IAEONSession holds token and user info."""
    session = IAEONSession(access_token="test_token", user_id="user123")
    assert session.access_token == "test_token"
    assert session.user_id == "user123"


def test_authenticator_init_manual():
    """Default OTP method is manual."""
    auth = IAEONAuthenticator(
        phone="090-1234-5678",
        password="password",
        otp_method="manual",
    )
    assert isinstance(auth._otp_handler, ManualOTPHandler)


def test_authenticator_init_custom_handler():
    """Custom OTP handler is accepted."""
    handler = MockOTPHandler()
    auth = IAEONAuthenticator(
        phone="090-1234-5678",
        password="password",
        otp_handler=handler,
    )
    assert auth._otp_handler is handler


@pytest.mark.asyncio
async def test_mock_otp_handler():
    """MockOTPHandler returns the configured code."""
    handler = MockOTPHandler("654321")
    code = await handler.get_otp_code("090-0000-0000")
    assert code == "654321"


@pytest.mark.asyncio
async def test_login_requires_iaeon_library(monkeypatch):
    """Login raises ImportError if iaeon is not installed."""
    handler = MockOTPHandler()
    auth = IAEONAuthenticator(
        phone="090-1234-5678",
        password="password",
        otp_handler=handler,
    )

    # The iaeon library is not installed, so this should raise ImportError
    with pytest.raises(ImportError, match="iaeon"):
        await auth.login()
