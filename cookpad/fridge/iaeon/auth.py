"""iAEON authentication wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .otp import BypassOTPHandler, ManualOTPHandler, OTPHandler


@dataclass
class IAEONSession:
    """Holds an authenticated iAEON session."""

    access_token: str
    device_id: str = ""
    raw: Any = None


class IAEONAuthenticator:
    """Wraps the iaeon library's authentication flow.

    Supports both manual OTP entry and automatic bypass.
    """

    def __init__(
        self,
        phone: str,
        password: str,
        otp_handler: OTPHandler | None = None,
        otp_method: str = "manual",
        device_id: str = "",
    ) -> None:
        self._phone = phone
        self._password = password
        self._device_id = device_id

        if otp_handler is not None:
            self._otp_handler = otp_handler
        elif otp_method == "bypass":
            self._otp_handler = BypassOTPHandler()
        else:
            self._otp_handler = ManualOTPHandler()

    async def login(self) -> IAEONSession:
        """Authenticate with iAEON and return a session.

        Uses iaeon.IAEONAuth.full_login() which is a sync function.
        The otp_provider callback bridges async OTPHandler → sync callback.

        Raises:
            ImportError: If the iaeon library is not installed.
            RuntimeError: If authentication fails.
        """
        try:
            from iaeon import IAEONAuth  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "iaeon ライブラリが必要です: pip install 'cookpad[iaeon]'\n"
                "iAEON連携を使用するには iaeon パッケージをインストールしてください"
            )

        import asyncio

        auth = IAEONAuth(device_id=self._device_id or None)

        # Bridge async OTPHandler to sync callback for full_login
        otp_handler = self._otp_handler
        phone = self._phone
        loop = asyncio.get_running_loop()

        def otp_provider() -> str:
            future = asyncio.run_coroutine_threadsafe(
                otp_handler.get_otp_code(phone), loop
            )
            return future.result(timeout=180)

        try:
            access_token = await asyncio.to_thread(
                auth.full_login, self._phone, self._password, otp_provider
            )
        except Exception as e:
            raise RuntimeError(f"iAEON認証に失敗しました: {e}") from e

        return IAEONSession(
            access_token=access_token,
            device_id=self._device_id,
            raw=auth,
        )
