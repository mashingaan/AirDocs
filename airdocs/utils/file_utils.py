# AirDocs - File Utilities
# ================================

import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import BinaryIO

from core.exceptions import FileOperationError

logger = logging.getLogger("airdocs.utils")


def calculate_file_hash(
    file_path: Path | str,
    algorithm: str = "sha256",
    buffer_size: int = 65536,
) -> str:
    """
    Calculate hash of a file.

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (sha256, md5, etc.)
        buffer_size: Buffer size for reading file

    Returns:
        Hex digest of file hash

    Raises:
        FileOperationError: If file cannot be read
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileOperationError(
            f"File not found: {file_path}",
            file_path=str(file_path),
            operation="hash",
        )

    try:
        hasher = hashlib.new(algorithm)

        with open(file_path, "rb") as f:
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                hasher.update(data)

        return hasher.hexdigest()

    except Exception as e:
        raise FileOperationError(
            f"Failed to calculate hash: {e}",
            file_path=str(file_path),
            operation="hash",
            cause=e,
        )


def get_file_size(file_path: Path | str) -> int:
    """
    Get file size in bytes.

    Args:
        file_path: Path to file

    Returns:
        File size in bytes

    Raises:
        FileOperationError: If file not found
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileOperationError(
            f"File not found: {file_path}",
            file_path=str(file_path),
            operation="size",
        )

    return file_path.stat().st_size


def copy_file(
    source: Path | str,
    destination: Path | str,
    overwrite: bool = False,
) -> Path:
    """
    Copy a file to a new location.

    Args:
        source: Source file path
        destination: Destination file path
        overwrite: Whether to overwrite existing file

    Returns:
        Path to copied file

    Raises:
        FileOperationError: If copy fails
    """
    source = Path(source)
    destination = Path(destination)

    if not source.exists():
        raise FileOperationError(
            f"Source file not found: {source}",
            file_path=str(source),
            operation="copy",
        )

    if destination.exists() and not overwrite:
        raise FileOperationError(
            f"Destination file exists: {destination}",
            file_path=str(destination),
            operation="copy",
        )

    try:
        # Ensure destination directory exists
        destination.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(source, destination)
        logger.debug(f"Copied file: {source} -> {destination}")
        return destination

    except Exception as e:
        raise FileOperationError(
            f"Failed to copy file: {e}",
            file_path=str(source),
            operation="copy",
            cause=e,
        )


def safe_delete(file_path: Path | str) -> bool:
    """
    Safely delete a file (with error handling).

    Args:
        file_path: Path to file

    Returns:
        True if file was deleted, False if it didn't exist
    """
    file_path = Path(file_path)

    if not file_path.exists():
        return False

    try:
        if file_path.is_file():
            file_path.unlink()
        elif file_path.is_dir():
            shutil.rmtree(file_path)

        logger.debug(f"Deleted: {file_path}")
        return True

    except Exception as e:
        logger.warning(f"Failed to delete {file_path}: {e}")
        return False


def ensure_directory(dir_path: Path | str) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        dir_path: Path to directory

    Returns:
        Path to directory

    Raises:
        FileOperationError: If directory cannot be created
    """
    dir_path = Path(dir_path)

    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    except Exception as e:
        raise FileOperationError(
            f"Failed to create directory: {e}",
            file_path=str(dir_path),
            operation="mkdir",
            cause=e,
        )


def get_unique_filename(
    directory: Path | str,
    base_name: str,
    extension: str,
) -> Path:
    """
    Get a unique filename in directory by adding counter if needed.

    Args:
        directory: Directory path
        base_name: Base filename without extension
        extension: File extension (with or without dot)

    Returns:
        Path to unique filename
    """
    directory = Path(directory)

    if not extension.startswith("."):
        extension = f".{extension}"

    # Try base name first
    path = directory / f"{base_name}{extension}"
    if not path.exists():
        return path

    # Add counter
    counter = 1
    while True:
        path = directory / f"{base_name}_{counter}{extension}"
        if not path.exists():
            return path
        counter += 1

        # Safety limit
        if counter > 10000:
            raise FileOperationError(
                f"Could not find unique filename after {counter} attempts",
                file_path=str(directory / base_name),
                operation="unique_name",
            )


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def list_files(
    directory: Path | str,
    pattern: str = "*",
    recursive: bool = False,
) -> list[Path]:
    """
    List files in a directory matching a pattern.

    Args:
        directory: Directory path
        pattern: Glob pattern (e.g., "*.pdf")
        recursive: Whether to search recursively

    Returns:
        List of file paths
    """
    directory = Path(directory)

    if not directory.exists():
        return []

    if recursive:
        return list(directory.rglob(pattern))
    else:
        return list(directory.glob(pattern))
