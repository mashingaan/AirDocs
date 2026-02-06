# AirDocs - Update System
# ===============================

import json
import logging
import shutil
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger("airdocs.utils")


@dataclass
class UpdateInfo:
    """Information about an available update."""
    version: str
    url: str
    sha256: str
    size: int
    release_date: str
    release_notes: str
    channel: str  # "latest" or "stable"


class UpdateError(Exception):
    """Base exception for update errors."""


class DownloadError(UpdateError):
    """Download failed."""


class ExtractionError(UpdateError):
    """Extraction failed."""


class VerificationError(UpdateError):
    """Verification failed."""


def check_for_updates(
    manifest_url: str,
    current_version: str,
    channel: str = "latest"
) -> UpdateInfo | None:
    """
    Check for available updates by fetching the manifest.

    Args:
        manifest_url: URL to the update manifest JSON
        current_version: Current application version
        channel: Update channel ("latest" or "stable")

    Returns:
        UpdateInfo if update available, None otherwise
    """
    logger.info(f"Checking for updates from {manifest_url}")

    try:
        response = requests.get(manifest_url, timeout=30)
        response.raise_for_status()
    except requests.ConnectionError as e:
        logger.warning(f"Connection error while checking updates: {e}")
        return None
    except requests.Timeout as e:
        logger.warning(f"Timeout while checking updates: {e}")
        return None
    except requests.HTTPError as e:
        logger.error(f"HTTP error while checking updates: {e}")
        return None

    try:
        manifest = response.json()
    except ValueError as e:
        logger.error(f"Failed to parse update manifest: {e}")
        return None

    # Get channel info
    channel_info = manifest.get(channel)
    if not channel_info:
        logger.warning(f"Channel '{channel}' not found in manifest")
        return None

    # Validate required fields
    required_fields = ['version', 'url', 'sha256']
    for field in required_fields:
        if field not in channel_info:
            logger.error(f"Missing required field '{field}' in manifest")
            return None

    # Compare versions
    from core.version import is_newer_version
    if not is_newer_version(current_version, channel_info['version']):
        logger.info("No update available")
        return None

    # Create and return UpdateInfo
    return UpdateInfo(
        version=channel_info['version'],
        url=channel_info['url'],
        sha256=channel_info['sha256'],
        size=channel_info.get('size', 0),
        release_date=channel_info.get('release_date', ''),
        release_notes=channel_info.get('release_notes', ''),
        channel=channel
    )


def check_disk_space_for_download(file_size: int, download_path: Path) -> bool:
    """
    Check if there is enough disk space for download.

    Args:
        file_size: Size of file to download in bytes
        download_path: Path where file will be saved

    Returns:
        True if enough space available
    """
    free_space = shutil.disk_usage(download_path.parent).free
    required_space = int(file_size * 1.5)  # For download and extraction
    return free_space >= required_space


def download_update(
    url: str,
    destination: Path,
    progress_callback=None
) -> bool:
    """
    Download update file with retry logic.

    Args:
        url: URL to download from
        destination: Path to save the file
        progress_callback: Optional callback(downloaded: int, total: int)

    Returns:
        True if download successful
    """
    max_retries = 3
    retry_delays = [1, 2, 4]
    last_error: Exception | None = None

    for attempt in range(max_retries):
        temp_file = destination.with_suffix('.tmp')

        try:
            # Clean up existing temp file
            if temp_file.exists():
                temp_file.unlink()

            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)

            # Success - move temp file to destination
            if destination.exists():
                destination.unlink()
            temp_file.rename(destination)

            logger.info(f"Download complete: {destination}")
            return True

        except Exception as e:
            last_error = e
            logger.warning(f"Download attempt {attempt + 1} failed: {e}")

            # Clean up temp file
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass

            # Wait before retry (except on last attempt)
            if attempt < max_retries - 1:
                time.sleep(retry_delays[attempt])

    error_message = f"Download failed after {max_retries} attempts"
    if last_error:
        error_message = f"{error_message}: {last_error}"
    logger.error(error_message)
    raise DownloadError(error_message)


def verify_update(zip_path: Path, expected_sha256: str) -> bool:
    """
    Verify downloaded update file integrity.

    Args:
        zip_path: Path to the downloaded ZIP file
        expected_sha256: Expected SHA256 hash

    Returns:
        True if hash matches
    """
    from utils.file_utils import calculate_file_hash

    actual_hash = calculate_file_hash(zip_path, algorithm='sha256')
    result = actual_hash.lower() == expected_sha256.lower()

    if not result:
        error_message = (
            f"Hash mismatch: expected {expected_sha256}, got {actual_hash}"
        )
        logger.error(error_message)
        raise VerificationError(error_message)

    return result


def extract_update_with_progress(
    zip_path: Path,
    extract_to: Path,
    progress_callback=None
) -> bool:
    """
    Extract ZIP with progress reporting.

    Args:
        zip_path: Path to ZIP file
        extract_to: Destination directory
        progress_callback: Optional callback(current: int, total: int)

    Returns:
        True if extraction successful
    """
    try:
        extract_to.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            names = zip_file.namelist()
            total = len(names)

            for index, name in enumerate(names, start=1):
                zip_file.extract(name, path=extract_to)
                if progress_callback:
                    progress_callback(index, total)

        return True
    except Exception as e:
        logger.error(f"Failed to extract update: {e}", exc_info=True)
        raise ExtractionError(str(e))


def download_and_prepare(update_info: UpdateInfo) -> bool:
    """
    Download update package (if needed), verify, extract, and create pending marker.

    Args:
        update_info: UpdateInfo for the target version

    Returns:
        True if update is prepared successfully, False otherwise
    """
    from core.app_context import get_context

    context = get_context()
    user_dir = context.user_dir if context.user_dir else context.app_dir / "data"
    download_path = user_dir / "updates"
    download_path.mkdir(parents=True, exist_ok=True)
    zip_path = download_path / f"update_{update_info.version}.zip"

    if update_info.size > 0:
        if not check_disk_space_for_download(update_info.size, download_path):
            logger.error("Not enough disk space for update download")
            return False

    if zip_path.exists():
        if update_info.size > 0 and zip_path.stat().st_size != update_info.size:
            zip_path.unlink()
        else:
            logger.info(f"Using existing update package: {zip_path}")

    if not zip_path.exists():
        try:
            download_update(update_info.url, zip_path)
        except DownloadError as e:
            logger.error(f"Update download failed: {e}")
            return False

    if update_info.sha256:
        try:
            verify_update(zip_path, update_info.sha256)
        except VerificationError as e:
            logger.error(f"Update verification failed: {e}")
            return False
    else:
        logger.warning("SHA256 not provided for update; skipping integrity check")

    extracted_path = download_path / f"extracted_v{update_info.version}"
    try:
        extract_update_with_progress(zip_path, extracted_path)
    except ExtractionError as e:
        logger.error(f"Update extraction failed: {e}")
        return False

    pending_marker = user_dir / '.pending_update'
    update_data = {
        'version': update_info.version,
        'extracted_path': str(extracted_path),
        'url': update_info.url,
        'sha256': update_info.sha256,
        'size': update_info.size,
        'release_date': update_info.release_date,
        'release_notes': update_info.release_notes,
        'channel': update_info.channel,
        'download_timestamp': datetime.utcnow().isoformat() + "Z",
    }

    try:
        with open(pending_marker, 'w', encoding='utf-8') as f:
            json.dump(update_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save pending update marker: {e}")
        return False

    return True


def record_update_attempt(
    version: str,
    previous_version: str,
    channel: str,
    install_method: str,
    download_size: int,
    download_duration: int,
    success: bool,
    error_message: str | None = None,
    rollback: bool = False
) -> None:
    """
    Record an update attempt in the database.

    Args:
        version: Target version
        previous_version: Version before update
        channel: Update channel
        install_method: "auto" or "manual"
        download_size: Size of downloaded file in bytes
        download_duration: Download time in seconds
        success: Whether installation succeeded
        error_message: Error message if failed
        rollback: Whether rollback occurred
    """
    from data.database import get_db

    db = get_db()
    with db.transaction() as cursor:
        cursor.execute("""
            INSERT INTO update_history
            (version, previous_version, channel, install_method, download_size,
             download_duration, install_success, error_message, rollback_occurred)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            version, previous_version, channel, install_method, download_size,
            download_duration, 1 if success else 0, error_message, 1 if rollback else 0
        ))
