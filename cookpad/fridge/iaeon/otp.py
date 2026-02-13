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
    """Retrieves OTP automatically using the bypass-otp-lib library."""

    def __init__(self) -> None:
        try:
            import bypass_otp_lib  # noqa: F401

            self._bypass = bypass_otp_lib
        except ImportError:
            raise ImportError(
                "bypass-otp-lib が必要です: pip install 'cookpad[bypass-otp]'\n"
                "または手動OTPモード (otp_method = 'manual') を使用してください"
            )

    async def get_otp_code(self, phone: str) -> str:
        return self._bypass.get_otp(phone)
