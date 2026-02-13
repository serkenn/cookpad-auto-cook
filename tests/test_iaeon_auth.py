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
    """IAEONSession holds token and device info."""
    session = IAEONSession(access_token="test_token", device_id="dev123")
    assert session.access_token == "test_token"
    assert session.device_id == "dev123"


def test_iaeon_session_defaults():
    """IAEONSession has sensible defaults."""
    session = IAEONSession(access_token="tok")
    assert session.device_id == ""
    assert session.raw is None


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


def test_authenticator_init_with_device_id():
    """device_id is stored on the authenticator."""
    auth = IAEONAuthenticator(
        phone="090-1234-5678",
        password="password",
        device_id="my-device-001",
    )
    assert auth._device_id == "my-device-001"


@pytest.mark.asyncio
async def test_mock_otp_handler():
    """MockOTPHandler returns the configured code."""
    handler = MockOTPHandler("654321")
    code = await handler.get_otp_code("090-0000-0000")
    assert code == "654321"


@pytest.mark.asyncio
async def test_login_without_iaeon_raises_import_error(monkeypatch):
    """Login raises ImportError if iaeon is not installed."""
    import sys

    # Temporarily hide iaeon from imports
    real_iaeon = sys.modules.pop("iaeon", None)
    monkeypatch.setitem(sys.modules, "iaeon", None)

    handler = MockOTPHandler()
    auth = IAEONAuthenticator(
        phone="090-1234-5678",
        password="password",
        otp_handler=handler,
    )

    try:
        with pytest.raises(ImportError, match="iaeon"):
            await auth.login()
    finally:
        # Restore iaeon module
        if real_iaeon is not None:
            sys.modules["iaeon"] = real_iaeon
        else:
            sys.modules.pop("iaeon", None)


@pytest.mark.asyncio
async def test_login_with_bad_credentials_raises_runtime_error():
    """Login with bad credentials raises RuntimeError."""
    try:
        import iaeon  # noqa: F401
    except ImportError:
        pytest.skip("iaeon not installed")

    handler = MockOTPHandler()
    auth = IAEONAuthenticator(
        phone="090-0000-0000",
        password="badpassword",
        otp_handler=handler,
    )

    with pytest.raises(RuntimeError, match="iAEON認証に失敗しました"):
        await auth.login()
