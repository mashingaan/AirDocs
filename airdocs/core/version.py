# AirDocs - Version Module
# ========================

import re
import logging
from typing import Tuple

logger = logging.getLogger("airdocs.core")

# SemVer format: MAJOR.MINOR.PATCH
VERSION = "0.2.3"
__version_info__ = (0, 2, 3)

# Version parsing regex
VERSION_PATTERN = re.compile(
    r'^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.-]+))?(?:\+([a-zA-Z0-9.-]+))?$'
)


def get_version() -> str:
    """Return current version string."""
    return VERSION


def parse_version(version: str) -> Tuple[int, int, int, str, str]:
    """
    Parse version string to tuple.

    Args:
        version: Version string in format MAJOR.MINOR.PATCH[-prerelease][+build]
                 Examples: "0.1.4", "1.0.0-beta.1", "2.3.5+20260108"

    Returns:
        Tuple of (major, minor, patch, prerelease, build)
    """
    if not version:
        logger.warning("Empty version string provided")
        return (0, 0, 0, "", "")

    clean_version = version.strip().lstrip("v")
    match = VERSION_PATTERN.match(clean_version)
    if not match:
        logger.warning(f"Failed to parse version: {version}")
        return (0, 0, 0, "", "")

    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    prerelease = match.group(4) or ""
    build = match.group(5) or ""

    return (major, minor, patch, prerelease, build)


def compare_versions(v1: str, v2: str) -> int:
    """
    Compare two version strings.

    Args:
        v1: First version string
        v2: Second version string

    Returns:
        -1 if v1 < v2, 0 if equal, 1 if v1 > v2
    
    Examples:
        compare_versions("1.0.0-beta.11", "1.0.0-beta.2") -> 1
        compare_versions("1.0.0", "1.0.0-rc.1") -> 1
    """
    parsed1 = parse_version(v1)
    parsed2 = parse_version(v2)

    # Compare major/minor/patch numerically
    for c1, c2 in zip(parsed1[:3], parsed2[:3]):
        if c1 < c2:
            return -1
        elif c1 > c2:
            return 1

    prerelease1 = parsed1[3]
    prerelease2 = parsed2[3]

    # Empty prerelease means stable release (greater than any prerelease)
    if prerelease1 == prerelease2:
        return 0
    if prerelease1 == "":
        return 1
    if prerelease2 == "":
        return -1

    # Compare prerelease identifiers per SemVer
    identifiers1 = prerelease1.split(".")
    identifiers2 = prerelease2.split(".")

    for id1, id2 in zip(identifiers1, identifiers2):
        id1_is_num = id1.isdigit()
        id2_is_num = id2.isdigit()

        if id1_is_num and id2_is_num:
            n1 = int(id1)
            n2 = int(id2)
            if n1 < n2:
                return -1
            if n1 > n2:
                return 1
        elif id1_is_num and not id2_is_num:
            return -1
        elif not id1_is_num and id2_is_num:
            return 1
        else:
            if id1 < id2:
                return -1
            if id1 > id2:
                return 1

    if len(identifiers1) < len(identifiers2):
        return -1
    if len(identifiers1) > len(identifiers2):
        return 1

    return 0


def is_newer_version(current: str, available: str) -> bool:
    """
    Check if available version is newer than current.

    Args:
        current: Current version string
        available: Available version string

    Returns:
        True if available > current
    """
    return compare_versions(current, available) < 0

