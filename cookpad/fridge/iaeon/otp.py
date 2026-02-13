"""OTP (One-Time Password) handling for iAEON authentication."""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod


class OTPHandler(ABC):
    """Abstract base class for OTP code retrieval."""

    @abstractmethod
    async def get_otp_code(self, phone: str) -> str:
        """Retrieve an OTP code for the given phone number.

        Args:
            phone: The phone number the OTP was sent to.

        Returns:
            The OTP code string.
        """
        ...


class ManualOTPHandler(OTPHandler):
    """Prompts the user to manually enter the OTP code from stdin."""

    async def get_otp_code(self, phone: str) -> str:
        print(f"SMSで送信されたOTPコードを入力してください ({phone}):")
        sys.stdout.flush()
        code = input("> ").strip()
        if not code:
            raise ValueError("OTPコードが入力されませんでした")
        return code


class BypassOTPHandler(OTPHandler):
    """Retrieves OTP automatically using the plusmsg-otp library.

    Connects to a +Message OTP relay running on an Android device.
    """

    def __init__(
        self,
        host: str = "192.168.1.1",
        port: int = 8765,
        otp_timeout: float = 120.0,
    ) -> None:
        try:
            from plusmsg_otp import PlusMessageOTP  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "plusmsg-otp が必要です: pip install plusmsg-otp\n"
                "または手動OTPモード (otp_method = 'manual') を使用してください"
            )
        self._client = PlusMessageOTP(host=host, port=port)
        self._otp_timeout = otp_timeout

    async def get_otp_code(self, phone: str) -> str:
        import asyncio

        # Clear old OTPs, then wait for new one (sync→async via to_thread)
        await asyncio.to_thread(self._client.clear)
        code = await asyncio.to_thread(
            self._client.wait_for_otp, self._otp_timeout
        )
        return code
