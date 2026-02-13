"""iAEON authentication wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .otp import BypassOTPHandler, ManualOTPHandler, OTPHandler


@dataclass
class IAEONSession:
    """Holds an authenticated iAEON session."""

    access_token: str
    user_id: str = ""
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
    ) -> None:
        self._phone = phone
        self._password = password

        if otp_handler is not None:
            self._otp_handler = otp_handler
        elif otp_method == "bypass":
            self._otp_handler = BypassOTPHandler()
        else:
            self._otp_handler = ManualOTPHandler()

    async def login(self) -> IAEONSession:
        """Authenticate with iAEON and return a session.

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

        auth = IAEONAuth(phone=self._phone, password=self._password)

        # Request OTP
        try:
            await auth.request_otp()
        except Exception as e:
            raise RuntimeError(f"OTP送信に失敗しました: {e}") from e

        # Get OTP code
        otp_code = await self._otp_handler.get_otp_code(self._phone)

        # Verify OTP and get tokens
        try:
            result = await auth.verify_otp(otp_code)
        except Exception as e:
            raise RuntimeError(f"OTP検証に失敗しました: {e}") from e

        return IAEONSession(
            access_token=result.get("access_token", ""),
            user_id=result.get("user_id", ""),
            raw=result,
        )
