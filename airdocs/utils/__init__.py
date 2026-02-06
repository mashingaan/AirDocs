# AirDocs - Utils Module
# =============================

from .file_utils import (
    calculate_file_hash,
    get_file_size,
    copy_file,
    safe_delete,
    ensure_directory,
)
from .path_builder import PathBuilder
from .field_mapper import FieldMapper
from .zip_utils import create_zip_archive, extract_zip

# Lazy imports for modules with external dependencies
def get_updater():
    from .updater import check_for_updates, download_update, verify_update
    return check_for_updates, download_update, verify_update

def get_data_migrator():
    from .data_migrator import detect_data_locations, migrate_data
    return detect_data_locations, migrate_data

def get_shortcut_creator():
    from .shortcut_creator import create_desktop_shortcut
    return create_desktop_shortcut

def get_system_info():
    from .system_info import generate_diagnostic_report
    return generate_diagnostic_report

def get_github_checker():
    from .github_checker import get_latest_release
    return get_latest_release

__all__ = [
    # File utils
    "calculate_file_hash",
    "get_file_size",
    "copy_file",
    "safe_delete",
    "ensure_directory",
    # Path builder
    "PathBuilder",
    # Field mapper
    "FieldMapper",
    # Zip utils
    "create_zip_archive",
    "extract_zip",
    # Lazy imports
    "get_updater",
    "get_data_migrator",
    "get_shortcut_creator",
    "get_system_info",
    "get_github_checker",
]
