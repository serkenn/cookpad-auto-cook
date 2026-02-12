"""Google Drive file upload via OAuth 2.0."""

from __future__ import annotations

from pathlib import Path


class GoogleDriveUploader:
    """Upload files to Google Drive using OAuth 2.0.

    On first use, opens a browser for Google account authorization.
    The token is saved for subsequent use.
    """

    SCOPES = ["https://www.googleapis.com/auth/drive.file"]

    def __init__(
        self,
        credentials_path: str | Path = "~/.config/cookpad/gdrive_credentials.json",
        token_path: str | Path = "~/.config/cookpad/gdrive_token.json",
        folder_id: str = "",
    ) -> None:
        self._credentials_path = Path(credentials_path).expanduser()
        self._token_path = Path(token_path).expanduser()
        self._folder_id = folder_id
        self._service = None

    def _get_service(self):
        """Build and return the Drive API service, authenticating if needed."""
        if self._service is not None:
            return self._service

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError:
            raise ImportError(
                "Google Drive 連携に必要なパッケージがインストールされていません:\n"
                "  pip install 'cookpad[gdrive]'"
            )

        creds = None

        # Load saved token
        if self._token_path.exists():
            creds = Credentials.from_authorized_user_file(
                str(self._token_path), self.SCOPES
            )

        # Refresh or get new credentials
        if creds is None or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self._credentials_path.exists():
                    raise FileNotFoundError(
                        f"OAuth クレデンシャルファイルが見つかりません: "
                        f"{self._credentials_path}\n"
                        f"Google Cloud Console からダウンロードしてください。"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self._credentials_path), self.SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save token for next time
            self._token_path.parent.mkdir(parents=True, exist_ok=True)
            self._token_path.write_text(creds.to_json())

        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def upload(
        self,
        file_path: str | Path,
        filename: str | None = None,
        folder_id: str | None = None,
    ) -> str:
        """Upload a file to Google Drive.

        Args:
            file_path: Path to the file to upload.
            filename: Name for the file in Drive. Defaults to local filename.
            folder_id: Drive folder ID. Uses configured default if None.

        Returns:
            The Google Drive file ID of the uploaded file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ImportError: If required packages are not installed.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

        from googleapiclient.http import MediaFileUpload

        service = self._get_service()
        target_folder = folder_id or self._folder_id

        file_metadata: dict = {
            "name": filename or file_path.name,
        }
        if target_folder:
            file_metadata["parents"] = [target_folder]

        media = MediaFileUpload(
            str(file_path),
            mimetype="application/pdf",
            resumable=True,
        )

        result = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )

        return result["id"]
