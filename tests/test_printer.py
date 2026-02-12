"""Tests for printer module."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cookpad.fridge.printer import Printer, PrinterInfo


class TestListPrinters:
    def test_list_printers_no_lpstat(self):
        """Raises RuntimeError when lpstat is not available."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="lpstat"):
                Printer.list_printers()

    def test_list_printers_with_printers(self):
        """Returns list of printers from lpstat output."""
        with patch("shutil.which", return_value="/usr/bin/lpstat"):
            default_result = MagicMock()
            default_result.returncode = 0
            default_result.stdout = "system default destination: HP_LaserJet\n"

            list_result = MagicMock()
            list_result.returncode = 0
            list_result.stdout = (
                "printer HP_LaserJet is idle.\n"
                "printer Brother_HL disabled since ...\n"
            )

            with patch(
                "subprocess.run",
                side_effect=[default_result, list_result],
            ):
                printers = Printer.list_printers()

        assert len(printers) == 2
        assert printers[0].name == "HP_LaserJet"
        assert printers[0].is_default is True
        assert printers[1].name == "Brother_HL"
        assert printers[1].is_default is False

    def test_list_printers_empty(self):
        """Returns empty list when no printers found."""
        with patch("shutil.which", return_value="/usr/bin/lpstat"):
            default_result = MagicMock()
            default_result.returncode = 1
            default_result.stdout = ""

            list_result = MagicMock()
            list_result.returncode = 0
            list_result.stdout = ""

            with patch(
                "subprocess.run",
                side_effect=[default_result, list_result],
            ):
                printers = Printer.list_printers()

        assert printers == []


class TestPrintFile:
    def test_print_file_not_found(self):
        """Raises FileNotFoundError for nonexistent file."""
        with pytest.raises(FileNotFoundError, match="ファイルが見つかりません"):
            Printer.print_file("/nonexistent/file.pdf")

    def test_print_file_no_lpr(self, tmp_path):
        """Raises RuntimeError when lpr is not available."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("dummy")

        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="lpr"):
                Printer.print_file(pdf_file)

    def test_print_file_default_printer(self, tmp_path):
        """Prints to default printer when no printer_name given."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("dummy")

        result = MagicMock()
        result.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/lpr"):
            with patch("subprocess.run", return_value=result) as mock_run:
                Printer.print_file(pdf_file)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "lpr"
        assert "-P" not in cmd
        assert str(pdf_file) in cmd

    def test_print_file_named_printer(self, tmp_path):
        """Prints to specific printer when printer_name given."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("dummy")

        result = MagicMock()
        result.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/lpr"):
            with patch("subprocess.run", return_value=result) as mock_run:
                Printer.print_file(pdf_file, printer_name="Brother_HL")

        cmd = mock_run.call_args[0][0]
        assert "-P" in cmd
        assert "Brother_HL" in cmd

    def test_print_file_failure(self, tmp_path):
        """Raises RuntimeError when lpr returns error."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("dummy")

        result = MagicMock()
        result.returncode = 1
        result.stderr = "No printer found"

        with patch("shutil.which", return_value="/usr/bin/lpr"):
            with patch("subprocess.run", return_value=result):
                with pytest.raises(RuntimeError, match="印刷に失敗"):
                    Printer.print_file(pdf_file)

    def test_print_file_timeout(self, tmp_path):
        """Raises RuntimeError on timeout."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("dummy")

        with patch("shutil.which", return_value="/usr/bin/lpr"):
            with patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="lpr", timeout=30),
            ):
                with pytest.raises(RuntimeError, match="タイムアウト"):
                    Printer.print_file(pdf_file)
