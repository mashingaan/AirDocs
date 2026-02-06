# AirDocs - ZIP Utilities
# ===============================

import logging
import zipfile
from pathlib import Path
from typing import Any

from core.exceptions import FileOperationError

logger = logging.getLogger("airdocs.utils")


def create_zip_archive(
    output_path: Path | str,
    files: list[Path | str] | dict[str, Path | str],
    base_dir: Path | str | None = None,
    compression: int = zipfile.ZIP_DEFLATED,
) -> Path:
    """
    Create a ZIP archive from files.

    Args:
        output_path: Path where to save the ZIP file
        files: Either a list of file paths or a dict of {archive_name: file_path}
        base_dir: Optional base directory to calculate relative paths
        compression: ZIP compression method

    Returns:
        Path to created ZIP file

    Raises:
        FileOperationError: If ZIP creation fails
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(output_path, "w", compression) as zf:
            if isinstance(files, dict):
                # Dict mapping archive names to file paths
                for archive_name, file_path in files.items():
                    file_path = Path(file_path)
                    if file_path.exists():
                        zf.write(file_path, archive_name)
                    else:
                        logger.warning(f"File not found, skipping: {file_path}")

            else:
                # List of file paths
                for file_path in files:
                    file_path = Path(file_path)
                    if not file_path.exists():
                        logger.warning(f"File not found, skipping: {file_path}")
                        continue

                    if base_dir:
                        # Use relative path from base_dir
                        try:
                            archive_name = file_path.relative_to(base_dir)
                        except ValueError:
                            archive_name = file_path.name
                    else:
                        archive_name = file_path.name

                    zf.write(file_path, archive_name)

        logger.info(f"Created ZIP archive: {output_path}")
        return output_path

    except Exception as e:
        raise FileOperationError(
            f"Failed to create ZIP archive: {e}",
            file_path=str(output_path),
            operation="zip_create",
            cause=e,
        )


def create_package_zip(
    output_path: Path | str,
    source_dir: Path | str,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> Path:
    """
    Create a ZIP archive from a directory.

    Args:
        output_path: Path where to save the ZIP file
        source_dir: Directory to archive
        include_patterns: Glob patterns for files to include (default: all)
        exclude_patterns: Glob patterns for files to exclude

    Returns:
        Path to created ZIP file
    """
    source_dir = Path(source_dir)
    output_path = Path(output_path)

    if not source_dir.exists():
        raise FileOperationError(
            f"Source directory not found: {source_dir}",
            file_path=str(source_dir),
            operation="zip_dir",
        )

    # Collect files to include
    if include_patterns:
        files = []
        for pattern in include_patterns:
            files.extend(source_dir.glob(pattern))
    else:
        files = list(source_dir.rglob("*"))

    # Filter out directories and excluded patterns
    files = [f for f in files if f.is_file()]

    if exclude_patterns:
        for pattern in exclude_patterns:
            excluded = set(source_dir.glob(pattern))
            files = [f for f in files if f not in excluded]

    return create_zip_archive(output_path, files, base_dir=source_dir)


def create_registry_zip(
    output_path: Path | str,
    registry_file: Path | str,
    document_files: list[Path | str],
    readme_content: str | None = None,
) -> Path:
    """
    Create a registry ZIP archive for 1C import.

    Standard structure:
    Реестр_<date>.zip
    ├── Реестр.xlsx
    ├── Документы/
    │   ├── AWB-123.pdf
    │   ├── Счет_123.pdf
    │   └── ...
    └── README.txt

    Args:
        output_path: Path where to save the ZIP file
        registry_file: Path to registry Excel file
        document_files: List of document file paths
        readme_content: Optional README content

    Returns:
        Path to created ZIP file
    """
    output_path = Path(output_path)
    registry_file = Path(registry_file)

    files_to_add = {}

    # Add registry file
    if registry_file.exists():
        files_to_add["Реестр.xlsx"] = registry_file
    else:
        logger.warning(f"Registry file not found: {registry_file}")

    # Add documents
    for doc_path in document_files:
        doc_path = Path(doc_path)
        if doc_path.exists():
            files_to_add[f"Документы/{doc_path.name}"] = doc_path
        else:
            logger.warning(f"Document file not found: {doc_path}")

    # Add README if provided
    if readme_content:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(readme_content)
            readme_path = Path(f.name)
        files_to_add["README.txt"] = readme_path

    result = create_zip_archive(output_path, files_to_add)

    # Clean up temp README
    if readme_content and readme_path.exists():
        readme_path.unlink()

    return result


def create_invoice_set_zip(
    output_path: Path | str,
    awb_number: str,
    client_type: str,
    document_files: list[Path | str],
) -> Path:
    """
    Create a document set ZIP for a client.

    Standard structure:
    Комплект_{client_type}_{date}.zip
    ├── AWB-{awb}.pdf
    ├── Счет_{awb}.pdf
    ├── УПД_{awb}.pdf
    └── ...

    Args:
        output_path: Path where to save the ZIP file
        awb_number: AWB number (for naming)
        client_type: Client type (TiA, FF, IP)
        document_files: List of document file paths

    Returns:
        Path to created ZIP file
    """
    output_path = Path(output_path)

    files_to_add = {}
    for doc_path in document_files:
        doc_path = Path(doc_path)
        if doc_path.exists():
            files_to_add[doc_path.name] = doc_path
        else:
            logger.warning(f"Document not found: {doc_path}")

    return create_zip_archive(output_path, files_to_add)


def extract_zip(
    zip_path: Path | str,
    output_dir: Path | str,
    members: list[str] | None = None,
) -> list[Path]:
    """
    Extract a ZIP archive.

    Args:
        zip_path: Path to ZIP file
        output_dir: Directory where to extract
        members: Optional list of specific members to extract

    Returns:
        List of extracted file paths

    Raises:
        FileOperationError: If extraction fails
    """
    zip_path = Path(zip_path)
    output_dir = Path(output_dir)

    if not zip_path.exists():
        raise FileOperationError(
            f"ZIP file not found: {zip_path}",
            file_path=str(zip_path),
            operation="zip_extract",
        )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        extracted = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            if members:
                for member in members:
                    if member in zf.namelist():
                        zf.extract(member, output_dir)
                        extracted.append(output_dir / member)
            else:
                zf.extractall(output_dir)
                extracted = [output_dir / name for name in zf.namelist()]

        logger.info(f"Extracted ZIP: {zip_path} -> {output_dir}")
        return extracted

    except Exception as e:
        raise FileOperationError(
            f"Failed to extract ZIP: {e}",
            file_path=str(zip_path),
            operation="zip_extract",
            cause=e,
        )


def list_zip_contents(zip_path: Path | str) -> list[dict[str, Any]]:
    """
    List contents of a ZIP archive.

    Args:
        zip_path: Path to ZIP file

    Returns:
        List of dicts with file info: {name, size, compressed_size, is_dir}
    """
    zip_path = Path(zip_path)

    if not zip_path.exists():
        return []

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            return [
                {
                    "name": info.filename,
                    "size": info.file_size,
                    "compressed_size": info.compress_size,
                    "is_dir": info.is_dir(),
                }
                for info in zf.infolist()
            ]
    except Exception as e:
        logger.error(f"Could not list ZIP contents: {e}")
        return []
