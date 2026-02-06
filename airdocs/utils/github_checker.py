# AirDocs - GitHub Release Checker
# =================================

import logging

import requests

from core.version import is_newer_version
from utils.updater import UpdateInfo

GITHUB_API_TIMEOUT = 10

logger = logging.getLogger("airdocs.utils")


def get_latest_release(repo: str, current_version: str) -> UpdateInfo | None:
    """
    Fetch latest release info from GitHub Releases API.

    Args:
        repo: Repository in "OWNER/REPO" format
        current_version: Current application version

    Returns:
        UpdateInfo if update available, None otherwise
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"

    try:
        response = requests.get(url, timeout=GITHUB_API_TIMEOUT)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            if response.status_code == 404:
                logger.info(f"No releases found for repo: {repo}")
                return None
            logger.error(f"HTTP error while checking releases: {e}", exc_info=True)
            return None
    except requests.ConnectionError as e:
        logger.warning(f"Connection error while checking releases: {e}", exc_info=True)
        return None
    except requests.Timeout as e:
        logger.warning(f"Timeout while checking releases: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error while checking releases: {e}", exc_info=True)
        return None

    try:
        data = response.json()
    except ValueError as e:
        logger.error(f"Failed to parse release JSON: {e}", exc_info=True)
        return None

    tag_name = (data.get("tag_name") or "").lstrip("v")
    body = data.get("body") or ""
    published_at = data.get("published_at") or ""
    assets = data.get("assets") or []

    if not is_newer_version(current_version, tag_name):
        return None

    zip_asset = None
    for asset in assets:
        name = asset.get("name") or ""
        if name.endswith(".zip"):
            zip_asset = asset
            break

    if not zip_asset:
        logger.error("No ZIP asset found for latest release")
        return None

    browser_download_url = zip_asset.get("browser_download_url") or ""
    size = zip_asset.get("size") or 0

    return UpdateInfo(
        version=tag_name,
        url=browser_download_url,
        sha256="",
        size=size,
        release_date=published_at,
        release_notes=body,
        channel="latest",
    )
