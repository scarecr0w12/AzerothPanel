"""
Backup & Restore service.

Supports five storage backends:
  local   – local filesystem path
  sftp    – remote SFTP server (requires paramiko)
  ftp     – remote FTP/FTPS server (stdlib ftplib)
  s3      – AWS S3 (requires boto3)
  gdrive  – Google Drive via service-account JSON (requires google-auth)
  onedrive – OneDrive (requires msal)

Config JSON schemas per type
─────────────────────────────
local:
  { "path": "/mnt/backups/azeroth" }

sftp:
  { "host": "…", "port": 22, "username": "…", "password": "…",
    "private_key": "PEM string or empty", "path": "/backups" }

ftp:
  { "host": "…", "port": 21, "username": "…", "password": "…",
    "path": "/backups", "tls": true }

s3:
  { "access_key_id": "…", "secret_access_key": "…",
    "bucket": "my-bucket", "region": "us-east-1", "prefix": "azeroth/" }

gdrive:
  { "service_account_json": "{…escaped JSON…}", "folder_id": "1abc…" }

onedrive:
  { "client_id": "…", "client_secret": "…", "tenant_id": "…",
    "folder_path": "/backups" }
"""
from __future__ import annotations

import asyncio
import ftplib
import io
import json
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Any

logger = logging.getLogger(__name__)

BACKUP_LOCAL_DEFAULT = "/opt/azerothpanel-backups"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_run(cmd: list[str], cwd: str | None = None, env: dict | None = None) -> tuple[int, str]:
    """Run a subprocess and return (returncode, combined stdout+stderr)."""
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, timeout=3600
        )
        return proc.returncode, proc.stdout or ""
    except FileNotFoundError:
        return -1, f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "Command timed out"


# ──────────────────────────────────────────────────────────────────────────────
# Database dump helpers
# ──────────────────────────────────────────────────────────────────────────────

def _dump_database(
    host: str, port: str, user: str, password: str,
    db_name: str, output_path: str,
) -> tuple[bool, str]:
    """Dump a MySQL database to a .sql file using mysqldump."""
    cmd = [
        "mysqldump",
        f"--host={host}", f"--port={port}",
        f"--user={user}", f"--password={password}",
        "--single-transaction", "--routines", "--triggers",
        "--add-drop-table", "--create-options",
        "--result-file", output_path,
        db_name,
    ]
    rc, out = _safe_run(cmd)
    if rc != 0:
        return False, out
    return True, output_path


def _import_database(
    host: str, port: str, user: str, password: str,
    db_name: str, sql_path: str,
) -> tuple[bool, str]:
    """Import a SQL file into a MySQL database."""
    cmd = [
        "mysql",
        f"--host={host}", f"--port={port}",
        f"--user={user}", f"--password={password}",
        db_name,
    ]
    try:
        with open(sql_path, "r", encoding="utf-8", errors="replace") as fh:
            proc = subprocess.run(
                cmd, stdin=fh,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, timeout=3600,
            )
        if proc.returncode != 0:
            return False, proc.stdout or ""
        return True, ""
    except FileNotFoundError:
        return False, "mysql command not found"
    except subprocess.TimeoutExpired:
        return False, "mysql import timed out"


# ──────────────────────────────────────────────────────────────────────────────
# Storage providers
# ──────────────────────────────────────────────────────────────────────────────

class LocalStorage:
    def __init__(self, cfg: dict):
        self.path = Path(cfg.get("path") or BACKUP_LOCAL_DEFAULT)

    def ensure_dir(self):
        self.path.mkdir(parents=True, exist_ok=True)

    def upload(self, local_file: Path, remote_name: str) -> None:
        self.ensure_dir()
        shutil.copy2(local_file, self.path / remote_name)

    def download(self, remote_name: str, local_file: Path) -> None:
        src = self.path / remote_name
        if not src.exists():
            raise FileNotFoundError(f"Backup not found: {remote_name}")
        shutil.copy2(src, local_file)

    def delete(self, remote_name: str) -> None:
        p = self.path / remote_name
        if p.exists():
            p.unlink()

    def list_files(self) -> list[dict]:
        if not self.path.exists():
            return []
        files = []
        for p in sorted(self.path.glob("*.tar.gz"), reverse=True):
            files.append({
                "filename": p.name,
                "size_bytes": p.stat().st_size,
                "modified": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
        return files

    def test(self) -> tuple[bool, str]:
        try:
            self.ensure_dir()
            test_file = self.path / ".ap_test"
            test_file.write_text("ok")
            test_file.unlink()
            return True, "OK"
        except Exception as exc:
            return False, str(exc)


class SftpStorage:
    def __init__(self, cfg: dict):
        self.host = cfg.get("host", "")
        self.port = int(cfg.get("port", 22))
        self.username = cfg.get("username", "")
        self.password = cfg.get("password", "")
        self.private_key = cfg.get("private_key", "")
        self.remote_path = cfg.get("path", "/backups")

    def _connect(self):
        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if self.private_key:
            key_file = io.StringIO(self.private_key)
            pkey = paramiko.RSAKey.from_private_key(key_file)
            client.connect(self.host, port=self.port, username=self.username, pkey=pkey, timeout=30)
        else:
            client.connect(self.host, port=self.port, username=self.username,
                           password=self.password, timeout=30)
        sftp = client.open_sftp()
        # Ensure remote dir exists
        try:
            sftp.stat(self.remote_path)
        except FileNotFoundError:
            parts = Path(self.remote_path).parts
            cur = ""
            for part in parts:
                cur = str(Path(cur) / part) if cur else part
                if not cur:
                    continue
                try:
                    sftp.stat(cur)
                except FileNotFoundError:
                    try:
                        sftp.mkdir(cur)
                    except Exception:
                        pass
        return client, sftp

    def upload(self, local_file: Path, remote_name: str) -> None:
        client, sftp = self._connect()
        try:
            sftp.put(str(local_file), f"{self.remote_path}/{remote_name}")
        finally:
            sftp.close(); client.close()

    def download(self, remote_name: str, local_file: Path) -> None:
        client, sftp = self._connect()
        try:
            sftp.get(f"{self.remote_path}/{remote_name}", str(local_file))
        finally:
            sftp.close(); client.close()

    def delete(self, remote_name: str) -> None:
        client, sftp = self._connect()
        try:
            sftp.remove(f"{self.remote_path}/{remote_name}")
        finally:
            sftp.close(); client.close()

    def list_files(self) -> list[dict]:
        client, sftp = self._connect()
        try:
            files = []
            for attr in sftp.listdir_attr(self.remote_path):
                if attr.filename.endswith(".tar.gz"):
                    files.append({
                        "filename": attr.filename,
                        "size_bytes": attr.st_size or 0,
                        "modified": datetime.fromtimestamp(
                            attr.st_mtime or 0, tz=timezone.utc
                        ).isoformat(),
                    })
            return sorted(files, key=lambda x: x["filename"], reverse=True)
        finally:
            sftp.close(); client.close()

    def test(self) -> tuple[bool, str]:
        try:
            client, sftp = self._connect()
            sftp.close(); client.close()
            return True, "OK"
        except Exception as exc:
            return False, str(exc)


class FtpStorage:
    def __init__(self, cfg: dict):
        self.host = cfg.get("host", "")
        self.port = int(cfg.get("port", 21))
        self.username = cfg.get("username", "")
        self.password = cfg.get("password", "")
        self.remote_path = cfg.get("path", "/backups")
        self.tls = bool(cfg.get("tls", False))

    def _connect(self):
        if self.tls:
            ftp = ftplib.FTP_TLS()
        else:
            ftp = ftplib.FTP()
        ftp.connect(self.host, self.port, timeout=30)
        ftp.login(self.username, self.password)
        if self.tls:
            ftp.prot_p()  # type: ignore[attr-defined]
        # Ensure remote dir
        try:
            ftp.cwd(self.remote_path)
        except ftplib.error_perm:
            ftp.mkd(self.remote_path)
            ftp.cwd(self.remote_path)
        return ftp

    def upload(self, local_file: Path, remote_name: str) -> None:
        ftp = self._connect()
        try:
            with open(local_file, "rb") as fh:
                ftp.storbinary(f"STOR {remote_name}", fh)
        finally:
            ftp.quit()

    def download(self, remote_name: str, local_file: Path) -> None:
        ftp = self._connect()
        try:
            with open(local_file, "wb") as fh:
                ftp.retrbinary(f"RETR {remote_name}", fh.write)
        finally:
            ftp.quit()

    def delete(self, remote_name: str) -> None:
        ftp = self._connect()
        try:
            ftp.delete(remote_name)
        finally:
            ftp.quit()

    def list_files(self) -> list[dict]:
        ftp = self._connect()
        try:
            files = []
            entries = []
            ftp.retrlines("LIST", entries.append)
            for line in entries:
                parts = line.split()
                if not parts:
                    continue
                name = parts[-1]
                if name.endswith(".tar.gz"):
                    try:
                        size = int(parts[4])
                    except (IndexError, ValueError):
                        size = 0
                    files.append({"filename": name, "size_bytes": size, "modified": ""})
            return sorted(files, key=lambda x: x["filename"], reverse=True)
        finally:
            ftp.quit()

    def test(self) -> tuple[bool, str]:
        try:
            ftp = self._connect()
            ftp.quit()
            return True, "OK"
        except Exception as exc:
            return False, str(exc)


class S3Storage:
    def __init__(self, cfg: dict):
        self.access_key_id = cfg.get("access_key_id", "")
        self.secret_access_key = cfg.get("secret_access_key", "")
        self.bucket = cfg.get("bucket", "")
        self.region = cfg.get("region", "us-east-1")
        self.prefix = cfg.get("prefix", "azeroth-backups/")
        if self.prefix and not self.prefix.endswith("/"):
            self.prefix += "/"

    def _client(self):
        import boto3
        return boto3.client(
            "s3",
            region_name=self.region,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
        )

    def upload(self, local_file: Path, remote_name: str) -> None:
        self._client().upload_file(str(local_file), self.bucket, f"{self.prefix}{remote_name}")

    def download(self, remote_name: str, local_file: Path) -> None:
        self._client().download_file(self.bucket, f"{self.prefix}{remote_name}", str(local_file))

    def delete(self, remote_name: str) -> None:
        self._client().delete_object(Bucket=self.bucket, Key=f"{self.prefix}{remote_name}")

    def list_files(self) -> list[dict]:
        response = self._client().list_objects_v2(Bucket=self.bucket, Prefix=self.prefix)
        files = []
        for obj in response.get("Contents", []):
            key = obj["Key"]
            name = key[len(self.prefix):]
            if name.endswith(".tar.gz"):
                files.append({
                    "filename": name,
                    "size_bytes": obj.get("Size", 0),
                    "modified": obj["LastModified"].isoformat() if obj.get("LastModified") else "",
                })
        return sorted(files, key=lambda x: x["filename"], reverse=True)

    def test(self) -> tuple[bool, str]:
        try:
            self._client().head_bucket(Bucket=self.bucket)
            return True, "OK"
        except Exception as exc:
            return False, str(exc)


class GoogleDriveStorage:
    """Uses a service account JSON to upload/manage files in Google Drive."""

    def __init__(self, cfg: dict):
        self.service_account_json = cfg.get("service_account_json", "")
        self.folder_id = cfg.get("folder_id", "")

    def _credentials(self):
        from google.oauth2 import service_account
        info = json.loads(self.service_account_json)
        scopes = ["https://www.googleapis.com/auth/drive"]
        return service_account.Credentials.from_service_account_info(info, scopes=scopes)

    def _get_access_token(self) -> str:
        import google.auth.transport.requests
        creds = self._credentials()
        request = google.auth.transport.requests.Request()
        creds.refresh(request)
        return creds.token  # type: ignore[return-value]

    def _find_file_id(self, filename: str) -> str | None:
        import httpx
        token = self._get_access_token()
        q = f"name = '{filename}' and '{self.folder_id}' in parents and trashed = false"
        r = httpx.get(
            "https://www.googleapis.com/drive/v3/files",
            params={"q": q, "fields": "files(id,name)"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        r.raise_for_status()
        items = r.json().get("files", [])
        return items[0]["id"] if items else None

    def upload(self, local_file: Path, remote_name: str) -> None:
        import httpx
        token = self._get_access_token()
        metadata = {"name": remote_name, "parents": [self.folder_id]}
        with open(local_file, "rb") as fh:
            data = fh.read()
        # Multipart upload
        boundary = "ap_backup_boundary"
        body = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n"
            f"--{boundary}\r\nContent-Type: application/gzip\r\n\r\n"
        ).encode() + data + f"\r\n--{boundary}--".encode()
        r = httpx.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
            content=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
            timeout=600,
        )
        r.raise_for_status()

    def download(self, remote_name: str, local_file: Path) -> None:
        import httpx
        token = self._get_access_token()
        file_id = self._find_file_id(remote_name)
        if not file_id:
            raise FileNotFoundError(f"File not found in Google Drive: {remote_name}")
        r = httpx.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            params={"alt": "media"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=600,
        )
        r.raise_for_status()
        local_file.write_bytes(r.content)

    def delete(self, remote_name: str) -> None:
        import httpx
        token = self._get_access_token()
        file_id = self._find_file_id(remote_name)
        if file_id:
            httpx.delete(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )

    def list_files(self) -> list[dict]:
        import httpx
        token = self._get_access_token()
        q = f"'{self.folder_id}' in parents and trashed = false and name contains '.tar.gz'"
        r = httpx.get(
            "https://www.googleapis.com/drive/v3/files",
            params={"q": q, "fields": "files(id,name,size,modifiedTime)", "pageSize": 100},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        r.raise_for_status()
        files = []
        for item in r.json().get("files", []):
            files.append({
                "filename": item["name"],
                "size_bytes": int(item.get("size", 0)),
                "modified": item.get("modifiedTime", ""),
            })
        return sorted(files, key=lambda x: x["filename"], reverse=True)

    def test(self) -> tuple[bool, str]:
        try:
            import httpx
            token = self._get_access_token()
            r = httpx.get(
                f"https://www.googleapis.com/drive/v3/files/{self.folder_id}",
                params={"fields": "id,name"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            r.raise_for_status()
            return True, "OK"
        except Exception as exc:
            return False, str(exc)


class OneDriveStorage:
    """Uses MSAL app-only (client credentials) flow to access OneDrive via Graph API."""

    def __init__(self, cfg: dict):
        self.client_id = cfg.get("client_id", "")
        self.client_secret = cfg.get("client_secret", "")
        self.tenant_id = cfg.get("tenant_id", "")
        self.folder_path = cfg.get("folder_path", "/backups").strip("/")
        self.drive_id = cfg.get("drive_id", "")  # optional: specific drive ID

    def _get_access_token(self) -> str:
        import msal
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in result:
            raise RuntimeError(f"OneDrive auth failed: {result.get('error_description', result)}")
        return result["access_token"]

    def _drive_base(self) -> str:
        if self.drive_id:
            return f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}"
        return "https://graph.microsoft.com/v1.0/me/drive"

    def _folder_path_url(self) -> str:
        base = self._drive_base()
        if self.folder_path:
            return f"{base}/root:/{self.folder_path}"
        return f"{base}/root"

    def upload(self, local_file: Path, remote_name: str) -> None:
        import httpx
        token = self._get_access_token()
        upload_url = f"{self._folder_path_url()}/{remote_name}:/content"
        with open(local_file, "rb") as fh:
            data = fh.read()
        r = httpx.put(
            upload_url,
            content=data,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
            timeout=600,
        )
        r.raise_for_status()

    def download(self, remote_name: str, local_file: Path) -> None:
        import httpx
        token = self._get_access_token()
        # Get download URL
        meta_url = f"{self._folder_path_url()}/{remote_name}"
        r = httpx.get(meta_url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        r.raise_for_status()
        download_url = r.json().get("@microsoft.graph.downloadUrl", "")
        if not download_url:
            raise FileNotFoundError(f"OneDrive file not found: {remote_name}")
        r2 = httpx.get(download_url, timeout=600)
        r2.raise_for_status()
        local_file.write_bytes(r2.content)

    def delete(self, remote_name: str) -> None:
        import httpx
        token = self._get_access_token()
        url = f"{self._folder_path_url()}/{remote_name}"
        httpx.delete(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)

    def list_files(self) -> list[dict]:
        import httpx
        token = self._get_access_token()
        url = f"{self._folder_path_url()}:/children"
        r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        r.raise_for_status()
        files = []
        for item in r.json().get("value", []):
            name = item.get("name", "")
            if name.endswith(".tar.gz"):
                files.append({
                    "filename": name,
                    "size_bytes": item.get("size", 0),
                    "modified": item.get("lastModifiedDateTime", ""),
                })
        return sorted(files, key=lambda x: x["filename"], reverse=True)

    def test(self) -> tuple[bool, str]:
        try:
            import httpx
            token = self._get_access_token()
            url = f"{self._folder_path_url()}"
            r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
            r.raise_for_status()
            return True, "OK"
        except Exception as exc:
            return False, str(exc)


def _get_storage(dest_type: str, config: dict):
    """Factory: return the appropriate storage object for the given type/config."""
    if dest_type == "local":
        return LocalStorage(config)
    if dest_type == "sftp":
        return SftpStorage(config)
    if dest_type == "ftp":
        return FtpStorage(config)
    if dest_type == "s3":
        return S3Storage(config)
    if dest_type == "gdrive":
        return GoogleDriveStorage(config)
    if dest_type == "onedrive":
        return OneDriveStorage(config)
    raise ValueError(f"Unknown destination type: {dest_type!r}")


# ──────────────────────────────────────────────────────────────────────────────
# Test connection  (sync, runs in executor from async context)
# ──────────────────────────────────────────────────────────────────────────────

def test_destination_sync(dest_type: str, config: dict) -> tuple[bool, str]:
    try:
        storage = _get_storage(dest_type, config)
        return storage.test()
    except Exception as exc:
        return False, str(exc)


def list_destination_files_sync(dest_type: str, config: dict) -> list[dict]:
    storage = _get_storage(dest_type, config)
    return storage.list_files()


def delete_destination_file_sync(dest_type: str, config: dict, filename: str) -> None:
    storage = _get_storage(dest_type, config)
    storage.delete(filename)


# ──────────────────────────────────────────────────────────────────────────────
# Main backup runner  (sync, called inside a thread executor)
# ──────────────────────────────────────────────────────────────────────────────

def run_backup_sync(
    job_id: int,
    dest_type: str | None,
    dest_config: dict,
    include_configs: bool,
    include_databases: bool,
    include_server_files: bool,
    settings: dict,
    progress_callback,      # callable(msg: str) – called with progress text lines
    instance_conf_files: list[tuple[str, str]] | None = None,
    # ^ list of (display_name, absolute_conf_path) for secondary worldserver instances
) -> tuple[str, str, int]:
    """
    Perform the backup synchronously (run in a thread executor).

    Returns (archive_filename, local_archive_path, size_bytes).
    Raises on error.  Calls progress_callback(msg) for each progress line.
    """
    timestamp = _now_iso()
    archive_name = f"azeroth-backup-{timestamp}.tar.gz"

    with tempfile.TemporaryDirectory(prefix="ap_backup_") as tmpdir:
        tmp = Path(tmpdir)
        progress_callback(f"[INFO] Backup started: {archive_name}")

        # ── 1. Configs ─────────────────────────────────────────────────────
        if include_configs:
            progress_callback("[INFO] Collecting config files…")
            conf_src = Path(settings.get("AC_CONF_PATH", ""))
            conf_dst = tmp / "configs"
            conf_dst.mkdir(parents=True, exist_ok=True)
            if conf_src.exists():
                for p in conf_src.rglob("*.conf"):
                    rel = p.relative_to(conf_src)
                    dst = conf_dst / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, dst)
                    progress_callback(f"  + {rel}")
            else:
                progress_callback(f"[WARN] AC_CONF_PATH not found: {conf_src}")

            # Per-instance config files (may live outside AC_CONF_PATH)
            if instance_conf_files:
                progress_callback("[INFO] Collecting per-instance config files…")
                for display_name, inst_conf_path in instance_conf_files:
                    inst_path = Path(inst_conf_path)
                    if not inst_path.exists():
                        progress_callback(f"[WARN] Instance config not found: {inst_conf_path} ({display_name})")
                        continue
                    # Sanitise display_name for use as a directory name
                    safe_name = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in display_name)
                    inst_dst = conf_dst / "instances" / safe_name / inst_path.name
                    inst_dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(inst_path, inst_dst)
                    progress_callback(f"  + instances/{safe_name}/{inst_path.name}")

        # ── 2. Databases ────────────────────────────────────────────────────
        if include_databases:
            progress_callback("[INFO] Dumping databases…")
            db_dir = tmp / "databases"
            db_dir.mkdir(parents=True, exist_ok=True)

            db_targets: list[tuple[str, str, str, str, str]] = [
                (
                    settings.get("AC_AUTH_DB_HOST", "127.0.0.1"),
                    settings.get("AC_AUTH_DB_PORT", "3306"),
                    settings.get("AC_AUTH_DB_USER", "acore"),
                    settings.get("AC_AUTH_DB_PASSWORD", "acore"),
                    settings.get("AC_AUTH_DB_NAME", "acore_auth"),
                ),
                (
                    settings.get("AC_CHAR_DB_HOST", "127.0.0.1"),
                    settings.get("AC_CHAR_DB_PORT", "3306"),
                    settings.get("AC_CHAR_DB_USER", "acore"),
                    settings.get("AC_CHAR_DB_PASSWORD", "acore"),
                    settings.get("AC_CHAR_DB_NAME", "acore_characters"),
                ),
                (
                    settings.get("AC_WORLD_DB_HOST", "127.0.0.1"),
                    settings.get("AC_WORLD_DB_PORT", "3306"),
                    settings.get("AC_WORLD_DB_USER", "acore"),
                    settings.get("AC_WORLD_DB_PASSWORD", "acore"),
                    settings.get("AC_WORLD_DB_NAME", "acore_world"),
                ),
            ]
            for host, port, user, pw, name in db_targets:
                if not name:
                    continue
                out_file = str(db_dir / f"{name}.sql")
                progress_callback(f"  Dumping {name}…")
                ok, msg = _dump_database(host, port, user, pw, name, out_file)
                if ok:
                    size_kb = Path(out_file).stat().st_size // 1024
                    progress_callback(f"  ✓ {name}: {size_kb} KB")
                else:
                    progress_callback(f"[WARN] Failed to dump {name}: {msg}")

        # ── 3. Server files ─────────────────────────────────────────────────
        if include_server_files:
            progress_callback("[INFO] Archiving server binaries…")
            bin_src = Path(settings.get("AC_BINARY_PATH", ""))
            bin_dst = tmp / "server_files"
            bin_dst.mkdir(parents=True, exist_ok=True)
            if bin_src.exists():
                for p in bin_src.iterdir():
                    if p.is_file():
                        shutil.copy2(p, bin_dst / p.name)
                        progress_callback(f"  + {p.name}")
            else:
                progress_callback(f"[WARN] AC_BINARY_PATH not found: {bin_src}")

        # ── 4. Create tar.gz archive ─────────────────────────────────────────
        progress_callback("[INFO] Creating archive…")
        archive_local = Path(tempfile.gettempdir()) / archive_name
        with tarfile.open(archive_local, "w:gz") as tar:
            tar.add(tmpdir, arcname=".")
        size_bytes = archive_local.stat().st_size
        progress_callback(f"[INFO] Archive size: {size_bytes // 1024} KB")

        # ── 5. Upload to destination ──────────────────────────────────────────
        local_dest_path = str(archive_local)
        if dest_type and dest_type != "local":
            progress_callback(f"[INFO] Uploading to {dest_type}…")
            try:
                storage = _get_storage(dest_type, dest_config)
                storage.upload(archive_local, archive_name)
                progress_callback("[INFO] Upload complete.")
                # Remove local temp archive after successful remote upload
                archive_local.unlink(missing_ok=True)
                local_dest_path = ""
            except Exception as exc:
                progress_callback(f"[ERROR] Upload failed: {exc}")
                raise
        else:
            # local destination – move to configured path
            local_cfg = LocalStorage(dest_config)
            local_cfg.ensure_dir()
            dest_file = local_cfg.path / archive_name
            shutil.move(str(archive_local), dest_file)
            local_dest_path = str(dest_file)
            progress_callback(f"[INFO] Saved to {local_dest_path}")

        progress_callback(f"[DONE] Backup complete: {archive_name}")
        return archive_name, local_dest_path, size_bytes


# ──────────────────────────────────────────────────────────────────────────────
# Restore runner  (sync, called inside a thread executor)
# ──────────────────────────────────────────────────────────────────────────────

def run_restore_sync(
    filename: str,
    local_path: str,
    dest_type: str | None,
    dest_config: dict,
    restore_configs: bool,
    restore_databases: bool,
    restore_server_files: bool,
    settings: dict,
    progress_callback,
    instance_conf_files: list[tuple[str, str]] | None = None,
    # ^ list of (display_name, absolute_conf_path) for secondary worldserver instances
) -> None:
    """
    Perform the restore synchronously (run in a thread executor).
    Calls progress_callback(msg) for each line.  Raises on error.
    """
    progress_callback(f"[INFO] Starting restore from: {filename}")

    with tempfile.TemporaryDirectory(prefix="ap_restore_") as tmpdir:
        tmp = Path(tmpdir)
        archive_local = tmp / filename

        # ── 1. Obtain archive ─────────────────────────────────────────────────
        if local_path and Path(local_path).exists():
            progress_callback("[INFO] Using local archive file…")
            shutil.copy2(local_path, archive_local)
        elif dest_type:
            progress_callback(f"[INFO] Downloading from {dest_type}…")
            storage = _get_storage(dest_type, dest_config)
            storage.download(filename, archive_local)
            progress_callback("[INFO] Download complete.")
        else:
            raise FileNotFoundError(f"Archive not available: {filename}")

        # ── 2. Extract ────────────────────────────────────────────────────────
        progress_callback("[INFO] Extracting archive…")
        extract_dir = tmp / "extracted"
        extract_dir.mkdir()
        with tarfile.open(archive_local, "r:gz") as tar:
            tar.extractall(extract_dir)

        # ── 3. Restore configs ────────────────────────────────────────────────
        if restore_configs:
            conf_src = extract_dir / "configs"
            conf_dst = Path(settings.get("AC_CONF_PATH", ""))
            if conf_src.exists() and conf_dst.exists():
                progress_callback("[INFO] Restoring config files…")
                for p in conf_src.rglob("*.conf"):
                    rel = p.relative_to(conf_src)
                    # Skip per-instance configs here; handled below
                    if rel.parts and rel.parts[0] == "instances":
                        continue
                    dst = conf_dst / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, dst)
                    progress_callback(f"  → {rel}")
            else:
                progress_callback("[WARN] No config backup found or target path missing.")

            # Restore per-instance config files to their original absolute paths
            if instance_conf_files:
                instances_src = (extract_dir / "configs" / "instances") if conf_src.exists() else None
                if instances_src and instances_src.exists():
                    progress_callback("[INFO] Restoring per-instance config files…")
                    for display_name, inst_conf_path in instance_conf_files:
                        safe_name = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in display_name)
                        inst_path = Path(inst_conf_path)
                        src_file = instances_src / safe_name / inst_path.name
                        if not src_file.exists():
                            progress_callback(f"[WARN] No backup found for instance config: {display_name}")
                            continue
                        inst_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_file, inst_path)
                        progress_callback(f"  → {inst_path} ({display_name})")

        # ── 4. Restore databases ───────────────────────────────────────────────
        if restore_databases:
            db_dir = extract_dir / "databases"
            if db_dir.exists():
                progress_callback("[INFO] Restoring databases…")
                db_targets: list[tuple[str, str, str, str, str]] = [
                    (
                        settings.get("AC_AUTH_DB_HOST", "127.0.0.1"),
                        settings.get("AC_AUTH_DB_PORT", "3306"),
                        settings.get("AC_AUTH_DB_USER", "acore"),
                        settings.get("AC_AUTH_DB_PASSWORD", "acore"),
                        settings.get("AC_AUTH_DB_NAME", "acore_auth"),
                    ),
                    (
                        settings.get("AC_CHAR_DB_HOST", "127.0.0.1"),
                        settings.get("AC_CHAR_DB_PORT", "3306"),
                        settings.get("AC_CHAR_DB_USER", "acore"),
                        settings.get("AC_CHAR_DB_PASSWORD", "acore"),
                        settings.get("AC_CHAR_DB_NAME", "acore_characters"),
                    ),
                    (
                        settings.get("AC_WORLD_DB_HOST", "127.0.0.1"),
                        settings.get("AC_WORLD_DB_PORT", "3306"),
                        settings.get("AC_WORLD_DB_USER", "acore"),
                        settings.get("AC_WORLD_DB_PASSWORD", "acore"),
                        settings.get("AC_WORLD_DB_NAME", "acore_world"),
                    ),
                ]
                for host, port, user, pw, name in db_targets:
                    sql_file = db_dir / f"{name}.sql"
                    if not sql_file.exists():
                        continue
                    progress_callback(f"  Importing {name}…")
                    ok, msg = _import_database(host, port, user, pw, name, str(sql_file))
                    if ok:
                        progress_callback(f"  ✓ {name}")
                    else:
                        progress_callback(f"[WARN] Failed to import {name}: {msg}")
            else:
                progress_callback("[WARN] No database backup found in archive.")

        # ── 5. Restore server files ────────────────────────────────────────────
        if restore_server_files:
            srv_src = extract_dir / "server_files"
            bin_dst = Path(settings.get("AC_BINARY_PATH", ""))
            if srv_src.exists() and bin_dst.exists():
                progress_callback("[INFO] Restoring server binaries…")
                for p in srv_src.iterdir():
                    if p.is_file():
                        shutil.copy2(p, bin_dst / p.name)
                        progress_callback(f"  → {p.name}")
            else:
                progress_callback("[WARN] No server files backup found or target path missing.")

        progress_callback("[DONE] Restore complete.")


# ──────────────────────────────────────────────────────────────────────────────
# Async wrappers (run sync work in default thread pool)
# ──────────────────────────────────────────────────────────────────────────────

async def run_backup_stream(
    job_id: int,
    dest_type: str | None,
    dest_config: dict,
    include_configs: bool,
    include_databases: bool,
    include_server_files: bool,
    settings: dict,
    instance_conf_files: list[tuple[str, str]] | None = None,
) -> AsyncIterator[tuple[str, str, str, int]]:
    """
    Async generator that yields (event_type, message) tuples.
    event_type is "log" during the process, then "result" once with
    (archive_name, local_path, size_bytes) encoded in the message JSON.
    Runs the actual work in a thread executor to keep the event loop free.
    """
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def _callback(msg: str):
        loop.call_soon_threadsafe(queue.put_nowait, msg)

    result_holder: list[Any] = []
    error_holder: list[str] = []

    def _do_work():
        try:
            result = run_backup_sync(
                job_id=job_id,
                dest_type=dest_type,
                dest_config=dest_config,
                include_configs=include_configs,
                include_databases=include_databases,
                include_server_files=include_server_files,
                settings=settings,
                progress_callback=_callback,
                instance_conf_files=instance_conf_files,
            )
            result_holder.append(result)
        except Exception as exc:
            error_holder.append(str(exc))
            _callback(f"[ERROR] {exc}")
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    future = loop.run_in_executor(None, _do_work)
    try:
        while True:
            msg = await queue.get()
            if msg is None:
                break
            yield "log", msg
    finally:
        await asyncio.wrap_future(future)

    if error_holder:
        yield "error", error_holder[0]
    elif result_holder:
        name, path, size = result_holder[0]
        yield "result", json.dumps({"filename": name, "local_path": path, "size_bytes": size})


async def run_restore_stream(
    filename: str,
    local_path: str,
    dest_type: str | None,
    dest_config: dict,
    restore_configs: bool,
    restore_databases: bool,
    restore_server_files: bool,
    settings: dict,
    instance_conf_files: list[tuple[str, str]] | None = None,
) -> AsyncIterator[tuple[str, str]]:
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def _callback(msg: str):
        loop.call_soon_threadsafe(queue.put_nowait, msg)

    error_holder: list[str] = []

    def _do_work():
        try:
            run_restore_sync(
                filename=filename,
                local_path=local_path,
                dest_type=dest_type,
                dest_config=dest_config,
                restore_configs=restore_configs,
                restore_databases=restore_databases,
                restore_server_files=restore_server_files,
                settings=settings,
                progress_callback=_callback,
                instance_conf_files=instance_conf_files,
            )
        except Exception as exc:
            error_holder.append(str(exc))
            _callback(f"[ERROR] {exc}")
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    future = loop.run_in_executor(None, _do_work)
    try:
        while True:
            msg = await queue.get()
            if msg is None:
                break
            yield "log", msg
    finally:
        await asyncio.wrap_future(future)

    if error_holder:
        yield "error", error_holder[0]
    else:
        yield "result", "ok"
