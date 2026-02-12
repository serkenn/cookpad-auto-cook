"""Print PDF files using lpr."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PrinterInfo:
    name: str
    is_default: bool


class Printer:
    """Print files using the system lpr command."""

    @staticmethod
    def list_printers() -> list[PrinterInfo]:
        """List available printers using lpstat.

        Returns:
            List of PrinterInfo with name and default status.

        Raises:
            RuntimeError: If lpstat is not available.
        """
        if shutil.which("lpstat") is None:
            raise RuntimeError(
                "lpstat コマンドが見つかりません。"
                "CUPS がインストールされているか確認してください:\n"
                "  Ubuntu/Debian: sudo apt install cups\n"
                "  Fedora/RHEL:   sudo dnf install cups"
            )

        # Get default printer
        default_name = ""
        try:
            result = subprocess.run(
                ["lpstat", "-d"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Output: "system default destination: PrinterName"
            if result.returncode == 0 and ":" in result.stdout:
                default_name = result.stdout.strip().split(":")[-1].strip()
        except (subprocess.TimeoutExpired, OSError):
            pass

        # List all printers
        printers: list[PrinterInfo] = []
        try:
            result = subprocess.run(
                ["lpstat", "-p"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    # "printer PrinterName is idle." or similar
                    parts = line.split()
                    if len(parts) >= 2 and parts[0] == "printer":
                        name = parts[1]
                        printers.append(
                            PrinterInfo(
                                name=name,
                                is_default=(name == default_name),
                            )
                        )
        except (subprocess.TimeoutExpired, OSError):
            pass

        return printers

    @staticmethod
    def print_file(
        file_path: str | Path,
        printer_name: str | None = None,
    ) -> None:
        """Print a file using lpr.

        Args:
            file_path: Path to the file to print.
            printer_name: Specific printer name. Uses default if None.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            RuntimeError: If lpr is not available or printing fails.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

        if shutil.which("lpr") is None:
            raise RuntimeError(
                "lpr コマンドが見つかりません。"
                "CUPS がインストールされているか確認してください:\n"
                "  Ubuntu/Debian: sudo apt install cups\n"
                "  Fedora/RHEL:   sudo dnf install cups"
            )

        cmd = ["lpr"]
        if printer_name:
            cmd.extend(["-P", printer_name])
        cmd.append(str(file_path))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"印刷に失敗しました: {result.stderr.strip()}"
                )
        except subprocess.TimeoutExpired:
            raise RuntimeError("印刷ジョブがタイムアウトしました。")
