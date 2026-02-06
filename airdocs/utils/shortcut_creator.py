# AirDocs - Desktop Shortcut Creator
# ==========================================

import logging
from pathlib import Path

logger = logging.getLogger("airdocs.utils")


def get_desktop_path() -> Path:
    """
    Get the path to the user's desktop.

    Returns:
        Path to desktop directory
    """
    import winreg

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
        )
        desktop = winreg.QueryValueEx(key, 'Desktop')[0]
        winreg.CloseKey(key)
        return Path(desktop)
    except (OSError, WindowsError) as e:
        logger.warning(f"Failed to get desktop path from registry: {e}")
        # Fallback to default location
        import os
        return Path(os.path.expanduser("~")) / "Desktop"


def create_desktop_shortcut(
    exe_path: Path,
    shortcut_name: str = "AirDocs"
) -> bool:
    """
    Create a desktop shortcut for the application.

    Args:
        exe_path: Path to the executable
        shortcut_name: Name for the shortcut

    Returns:
        True if shortcut created successfully
    """
    try:
        import win32com.client

        desktop_path = get_desktop_path()
        shortcut_path = desktop_path / f"{shortcut_name}.lnk"

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.Targetpath = str(exe_path)
        shortcut.WorkingDirectory = str(exe_path.parent)
        shortcut.IconLocation = str(exe_path)
        shortcut.Description = "AirDocs - Logistics Document Management"
        shortcut.save()

        logger.info(f"Desktop shortcut created: {shortcut_path}")
        return True

    except ImportError:
        logger.warning("win32com not available, cannot create shortcut")
        return False
    except Exception as e:
        logger.warning(f"Failed to create desktop shortcut: {e}")
        return False


def remove_desktop_shortcut(shortcut_name: str = "AirDocs") -> bool:
    """
    Remove desktop shortcut if it exists.

    Args:
        shortcut_name: Name of the shortcut

    Returns:
        True if removed or didn't exist
    """
    try:
        desktop_path = get_desktop_path()
        shortcut_path = desktop_path / f"{shortcut_name}.lnk"

        if shortcut_path.exists():
            shortcut_path.unlink()
            logger.info(f"Desktop shortcut removed: {shortcut_path}")

        return True
    except Exception as e:
        logger.warning(f"Failed to remove desktop shortcut: {e}")
        return False
