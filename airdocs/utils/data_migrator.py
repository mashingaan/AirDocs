# AirDocs - Data Migration Utility
# =======================================

import logging
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("airdocs.utils")


@dataclass
class DataInfo:
    """Information about a data location."""
    size_bytes: int
    record_count: int  # Number of shipments in DB
    last_modified: datetime
    db_exists: bool


@dataclass
class DataLocationInfo:
    """Information about available data locations."""
    has_app_data: bool
    has_user_data: bool
    app_data_path: Path | None
    user_data_path: Path | None
    app_data_info: DataInfo | None
    user_data_info: DataInfo | None


@dataclass
class MigrationResult:
    """Result of data migration."""
    success: bool
    error: str | None
    backup_path: Path | None


def get_data_info(data_path: Path) -> DataInfo:
    """
    Get information about data at the given path.

    Args:
        data_path: Path to data directory

    Returns:
        DataInfo with size, record count, and modification date
    """
    # Calculate directory size
    size = 0
    for f in data_path.rglob('*'):
        if f.is_file():
            try:
                size += f.stat().st_size
            except OSError:
                pass

    # Check for database
    db_path = data_path / 'airdocs.db'
    db_exists = db_path.exists()
    record_count = 0
    last_modified = datetime.fromtimestamp(0)

    if db_exists:
        try:
            last_modified = datetime.fromtimestamp(db_path.stat().st_mtime)

            # Count records
            conn = sqlite3.connect(str(db_path))
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM shipments")
                record_count = cursor.fetchone()[0]
            except sqlite3.Error:
                pass
            finally:
                conn.close()
        except OSError:
            pass

    return DataInfo(
        size_bytes=size,
        record_count=record_count,
        last_modified=last_modified,
        db_exists=db_exists
    )


def detect_data_locations() -> DataLocationInfo:
    """
    Detect available data locations.

    Returns:
        DataLocationInfo with information about app and user data paths
    """
    from core.app_context import get_context

    context = get_context()

    # Check app data (in app folder)
    app_data_path = context.app_dir / 'data'
    has_app_data = app_data_path.exists() and (app_data_path / 'airdocs.db').exists()
    app_data_info = get_data_info(app_data_path) if has_app_data else None

    # Check user data (in %APPDATA%)
    user_data_path = context.user_dir
    has_user_data = False
    user_data_info = None

    if user_data_path and user_data_path.exists():
        db_path = user_data_path / 'airdocs.db'
        if db_path.exists():
            has_user_data = True
            user_data_info = get_data_info(user_data_path)

    return DataLocationInfo(
        has_app_data=has_app_data,
        has_user_data=has_user_data,
        app_data_path=app_data_path if has_app_data else None,
        user_data_path=user_data_path if has_user_data else None,
        app_data_info=app_data_info,
        user_data_info=user_data_info
    )


def _is_writable(directory: Path) -> bool:
    """
    Check if directory is writable.

    Args:
        directory: Path to check

    Returns:
        True if writable
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
        test_file = directory / '.write_test'
        test_file.write_text('test')
        test_file.unlink()
        return True
    except (OSError, PermissionError):
        return False


def _ignore_locked_files(directory: str, files: list[str]) -> list[str]:
    """
    Ignore function for shutil.copytree to skip locked/temporary files.

    Skips:
    - Log files (*.log) - may be locked by logging
    - Lock files (*.lock, *.db-lock)
    - Temp files (.write_test)
    - The entire 'logs' directory (recreated on startup)
    """
    ignored = []
    dir_path = Path(directory)

    for f in files:
        file_path = dir_path / f

        # Skip logs directory entirely
        if f == 'logs' and file_path.is_dir():
            ignored.append(f)
            continue

        # Skip log files
        if f.endswith('.log'):
            ignored.append(f)
            continue

        # Skip lock files
        if f.endswith('.lock') or f.endswith('.db-lock'):
            ignored.append(f)
            continue

        # Skip temp test files
        if f == '.write_test':
            ignored.append(f)
            continue

    return ignored


def create_data_backup(data_path: Path) -> Path:
    """
    Create a backup of data directory.

    Args:
        data_path: Path to data to backup

    Returns:
        Path to backup directory
    """
    backup_dir = data_path.parent / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"data_backup_{timestamp}"
    backup_path = backup_dir / backup_name

    shutil.copytree(data_path, backup_path, ignore=_ignore_locked_files)
    logger.info(f"Data backup created: {backup_path}")

    return backup_path


def migrate_data(
    source: Path,
    destination: Path,
    create_backup: bool = True
) -> MigrationResult:
    """
    Migrate data from source to destination with verification.

    Args:
        source: Source data directory
        destination: Destination data directory
        create_backup: Whether to backup existing destination

    Returns:
        MigrationResult with success status and backup path
    """
    # Pre-checks
    if not source.exists():
        return MigrationResult(False, f"Source path does not exist: {source}", None)

    # Calculate source size
    source_size = sum(
        f.stat().st_size for f in source.rglob('*') if f.is_file()
    )

    # Check destination disk space
    try:
        free_space = shutil.disk_usage(destination.parent).free
        if free_space < source_size * 1.5:
            return MigrationResult(
                False,
                f"Insufficient disk space. Required: {source_size * 1.5 / 1024 / 1024:.1f} MB, "
                f"Available: {free_space / 1024 / 1024:.1f} MB",
                None
            )
    except OSError as e:
        return MigrationResult(False, f"Cannot check disk space: {e}", None)

    # Check destination writable
    if not _is_writable(destination.parent):
        return MigrationResult(False, "Destination is not writable", None)

    # Backup existing destination if needed
    backup_path = None
    if create_backup and destination.exists():
        try:
            backup_path = create_data_backup(destination)
        except Exception as e:
            return MigrationResult(False, f"Failed to create backup: {e}", None)

    # Atomic migration using temp directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = destination.parent / f'.migration_temp_{timestamp}'

    try:
        # Copy to temp (skip locked files like logs)
        shutil.copytree(source, temp_dir, ignore=_ignore_locked_files)

        # Verify copy
        temp_db = temp_dir / 'airdocs.db'
        source_db = source / 'airdocs.db'

        if source_db.exists():
            if not temp_db.exists():
                raise Exception("Database not copied")

            # Verify sizes match
            if temp_db.stat().st_size != source_db.stat().st_size:
                raise Exception("Database size mismatch after copy")

        # Count files (excluding ignored files for comparison)
        def count_non_ignored(path: Path) -> int:
            count = 0
            for f in path.rglob('*'):
                # Skip logs directory and its contents
                if 'logs' in f.parts:
                    continue
                # Skip log files
                if f.suffix == '.log':
                    continue
                # Skip lock files
                if f.suffix in ('.lock', '.db-lock') or f.name.endswith('.db-lock'):
                    continue
                # Skip temp files
                if f.name == '.write_test':
                    continue
                count += 1
            return count

        source_files = count_non_ignored(source)
        temp_files = len(list(temp_dir.rglob('*')))
        if source_files != temp_files:
            logger.warning(f"File count differs: source={source_files}, copied={temp_files} (some files may be excluded)")

        # Replace destination - use copytree with dirs_exist_ok for locked files
        if destination.exists():
            # Can't rename over existing dir, so copy contents instead
            shutil.copytree(
                temp_dir, destination,
                dirs_exist_ok=True,
                ignore=_ignore_locked_files
            )
            # Clean up temp dir
            shutil.rmtree(temp_dir, ignore_errors=True)
        else:
            # No existing destination, can just rename
            temp_dir.rename(destination)

        # Create migration marker
        marker = destination / '.migrated'
        marker.write_text(f"Migrated from {source} on {datetime.now().isoformat()}")

        logger.info(f"Data migrated successfully from {source} to {destination}")

        return MigrationResult(True, None, backup_path)

    except Exception as e:
        logger.error(f"Migration failed: {e}")

        # Cleanup temp dir
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except OSError:
                pass

        # Restore from backup if available
        if backup_path and backup_path.exists():
            try:
                shutil.copytree(
                    backup_path, destination,
                    dirs_exist_ok=True,
                    ignore=_ignore_locked_files
                )
                logger.info("Restored from backup after failed migration")
            except OSError as restore_error:
                logger.error(f"Failed to restore from backup: {restore_error}")

        return MigrationResult(False, str(e), backup_path)
