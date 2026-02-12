"""Tests for Google Drive uploader."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cookpad.fridge.gdrive import GoogleDriveUploader


def _mock_googleapiclient():
    """Context manager that mocks googleapiclient.http.MediaFileUpload."""
    mock_http = MagicMock()
    mock_api = MagicMock()
    mock_api.http = mock_http
    return patch.dict("sys.modules", {
        "googleapiclient": mock_api,
        "googleapiclient.http": mock_http,
    })


class TestGoogleDriveUploader:
    def test_init_defaults(self):
        """Initializes with default paths."""
        uploader = GoogleDriveUploader()
        assert "gdrive_credentials.json" in str(uploader._credentials_path)
        assert "gdrive_token.json" in str(uploader._token_path)
        assert uploader._folder_id == ""

    def test_init_custom_paths(self, tmp_path):
        """Initializes with custom paths."""
        creds = tmp_path / "creds.json"
        token = tmp_path / "token.json"
        uploader = GoogleDriveUploader(
            credentials_path=str(creds),
            token_path=str(token),
            folder_id="folder123",
        )
        assert uploader._credentials_path == creds
        assert uploader._token_path == token
        assert uploader._folder_id == "folder123"

    def test_upload_file_not_found(self):
        """Raises FileNotFoundError for nonexistent file."""
        uploader = GoogleDriveUploader()
        uploader._service = MagicMock()

        with pytest.raises(FileNotFoundError, match="ファイルが見つかりません"):
            uploader.upload("/nonexistent/file.pdf")

    def test_upload_success(self, tmp_path):
        """Uploads file and returns file ID."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("dummy pdf content")

        uploader = GoogleDriveUploader(folder_id="folder123")

        mock_service = MagicMock()
        mock_files = MagicMock()
        mock_create = MagicMock()
        mock_create.execute.return_value = {"id": "file_abc123"}
        mock_files.create.return_value = mock_create
        mock_service.files.return_value = mock_files
        uploader._service = mock_service

        with _mock_googleapiclient():
            file_id = uploader.upload(pdf_file, filename="献立.pdf")

        assert file_id == "file_abc123"
        call_kwargs = mock_files.create.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
        assert body["name"] == "献立.pdf"
        assert body["parents"] == ["folder123"]

    def test_upload_default_filename(self, tmp_path):
        """Uses local filename when no filename specified."""
        pdf_file = tmp_path / "output.pdf"
        pdf_file.write_text("dummy")

        uploader = GoogleDriveUploader()
        mock_service = MagicMock()
        mock_files = MagicMock()
        mock_create = MagicMock()
        mock_create.execute.return_value = {"id": "file_xyz"}
        mock_files.create.return_value = mock_create
        mock_service.files.return_value = mock_files
        uploader._service = mock_service

        with _mock_googleapiclient():
            file_id = uploader.upload(pdf_file)

        call_kwargs = mock_files.create.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
        assert body["name"] == "output.pdf"

    def test_upload_no_folder(self, tmp_path):
        """No parents key when folder_id is empty."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("dummy")

        uploader = GoogleDriveUploader()
        mock_service = MagicMock()
        mock_files = MagicMock()
        mock_create = MagicMock()
        mock_create.execute.return_value = {"id": "file_123"}
        mock_files.create.return_value = mock_create
        mock_service.files.return_value = mock_files
        uploader._service = mock_service

        with _mock_googleapiclient():
            uploader.upload(pdf_file)

        call_kwargs = mock_files.create.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
        assert "parents" not in body

    def test_upload_override_folder(self, tmp_path):
        """folder_id parameter overrides configured default."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("dummy")

        uploader = GoogleDriveUploader(folder_id="default_folder")
        mock_service = MagicMock()
        mock_files = MagicMock()
        mock_create = MagicMock()
        mock_create.execute.return_value = {"id": "file_456"}
        mock_files.create.return_value = mock_create
        mock_service.files.return_value = mock_files
        uploader._service = mock_service

        with _mock_googleapiclient():
            uploader.upload(pdf_file, folder_id="override_folder")

        call_kwargs = mock_files.create.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
        assert body["parents"] == ["override_folder"]

    def test_get_service_no_credentials_file(self, tmp_path):
        """Raises FileNotFoundError when credentials file missing."""
        uploader = GoogleDriveUploader(
            credentials_path=str(tmp_path / "nonexistent.json"),
            token_path=str(tmp_path / "token.json"),
        )

        mock_creds_module = MagicMock()
        mock_creds_class = MagicMock()
        mock_creds_module.Credentials = mock_creds_class

        with patch.dict("sys.modules", {
            "google": MagicMock(),
            "google.auth": MagicMock(),
            "google.auth.transport": MagicMock(),
            "google.auth.transport.requests": MagicMock(),
            "google.oauth2": MagicMock(),
            "google.oauth2.credentials": mock_creds_module,
            "google_auth_oauthlib": MagicMock(),
            "google_auth_oauthlib.flow": MagicMock(),
            "googleapiclient": MagicMock(),
            "googleapiclient.discovery": MagicMock(),
        }):
            mock_creds_class.from_authorized_user_file.side_effect = Exception
            with pytest.raises(FileNotFoundError, match="クレデンシャル"):
                uploader._get_service()
