# AirDocs - System Information Utility
# ===========================================

import logging
import os
import platform
import socket
import locale
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("airdocs.utils")


def get_system_info() -> dict:
    """
    Get system information.

    Returns:
        Dictionary with system details
    """
    return {
        'os_name': platform.system(),
        'os_version': platform.version(),
        'os_release': platform.release(),
        'architecture': platform.machine(),
        'computer_name': socket.gethostname(),
        'username': os.getenv('USERNAME', 'unknown'),
        'locale': locale.getdefaultlocale()[0] or 'unknown',
        'timezone': datetime.now().astimezone().tzname()
    }


def get_network_info() -> dict:
    """
    Get network information.

    Returns:
        Dictionary with network details
    """
    info = {}

    # Local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info['local_ip'] = s.getsockname()[0]
        s.close()
    except Exception:
        info['local_ip'] = 'Unknown'

    # DNS servers (Windows)
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r'SYSTEM\CurrentControlSet\Services\Tcpip\Parameters'
        )
        dns = winreg.QueryValueEx(key, 'NameServer')[0]
        winreg.CloseKey(key)
        info['dns_servers'] = dns if dns else 'DHCP'
    except Exception:
        info['dns_servers'] = 'Unknown'

    # Proxy
    try:
        proxies = urllib.request.getproxies()
        info['proxy'] = proxies.get('http', 'Not configured')
    except Exception:
        info['proxy'] = 'Unknown'

    return info


def get_installed_packages() -> dict:
    """
    Get versions of installed packages.

    Returns:
        Dictionary with package versions
    """
    packages = {
        'python': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    }

    key_packages = ['PySide6', 'requests', 'reportlab', 'openpyxl', 'python-docx', 'PyPDF2', 'pypdf']

    try:
        import importlib.metadata
        for pkg in key_packages:
            try:
                version = importlib.metadata.version(pkg)
                packages[pkg] = version
            except Exception:
                packages[pkg] = 'Not installed'
    except ImportError:
        # Python < 3.8
        pass

    return packages


def get_database_stats(db_path: Path) -> dict:
    """
    Get database statistics.

    Args:
        db_path: Path to database file

    Returns:
        Dictionary with database stats
    """
    stats = {}

    if not db_path.exists():
        return {'error': 'Database not found'}

    stats['size_bytes'] = db_path.stat().st_size
    stats['size_mb'] = round(stats['size_bytes'] / 1024 / 1024, 2)

    try:
        from data.database import get_db

        db = get_db()

        # Schema version
        row = db.fetch_one("SELECT MAX(version) as version FROM schema_version")
        stats['schema_version'] = row['version'] if row else 0

        # Record counts
        tables = ['shipments', 'documents', 'parties']
        for table in tables:
            try:
                row = db.fetch_one(f"SELECT COUNT(*) as count FROM {table}")
                stats[f'{table}_count'] = row['count'] if row else 0
            except Exception:
                stats[f'{table}_count'] = 0

        # Last backup
        from core.app_context import get_context
        context = get_context()
        backup_dir = context.user_dir / 'backups' if context.user_dir else None

        if backup_dir and backup_dir.exists():
            backups = sorted(
                backup_dir.glob('*.db'),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            if backups:
                stats['last_backup'] = datetime.fromtimestamp(
                    backups[0].stat().st_mtime
                ).strftime('%Y-%m-%d %H:%M:%S')
            else:
                stats['last_backup'] = 'Never'
        else:
            stats['last_backup'] = 'Never'

    except Exception as e:
        stats['error'] = str(e)

    return stats


def get_recent_logs(log_path: Path, error_count: int = 20, warning_count: int = 10) -> dict:
    """
    Extract recent errors and warnings from log file.

    Args:
        log_path: Path to log file
        error_count: Number of recent errors to include
        warning_count: Number of recent warnings to include

    Returns:
        Dictionary with errors and warnings lists
    """
    logs = {'errors': [], 'warnings': []}

    if not log_path.exists():
        return logs

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Extract last ERROR lines
        errors = [line.strip() for line in lines if 'ERROR' in line]
        logs['errors'] = errors[-error_count:] if len(errors) > error_count else errors

        # Extract last WARNING lines
        warnings = [line.strip() for line in lines if 'WARNING' in line]
        logs['warnings'] = warnings[-warning_count:] if len(warnings) > warning_count else warnings

    except Exception as e:
        logs['error'] = str(e)

    return logs


def generate_diagnostic_report() -> str:
    """
    Generate a full diagnostic report.

    Returns:
        Formatted diagnostic report string
    """
    from core.app_context import get_context
    from core.version import VERSION
    from integrations.environment_checker import EnvironmentChecker

    context = get_context()

    # Collect all information
    system_info = get_system_info()
    network_info = get_network_info()
    packages = get_installed_packages()
    db_stats = get_database_stats(context.get_path('database'))
    logs = get_recent_logs(context.get_path('logs_dir') / 'app.log')

    # Environment check
    checker = EnvironmentChecker()
    env_status = checker.check_all()

    # Format report
    lines = [
        "=" * 80,
        "AWB DISPATCHER - DIAGNOSTIC REPORT",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 80,
        "",
        "APPLICATION INFORMATION",
        "-" * 80,
        f"Version:                {VERSION}",
        f"Python Version:         {packages['python']}",
        f"PySide6 Version:        {packages.get('PySide6', 'Unknown')}",
        f"Installation Path:      {context.app_dir}",
        f"Data Path:              {context.user_dir}",
        f"Portable Mode:          {'Yes' if context.user_dir == context.app_dir / 'data' else 'No'}",
        "",
        "SYSTEM INFORMATION",
        "-" * 80,
        f"Operating System:       {system_info['os_name']} {system_info['os_release']} ({system_info['os_version']})",
        f"Architecture:           {system_info['architecture']}",
        f"Computer Name:          {system_info['computer_name']}",
        f"Username:               {system_info['username']}",
        f"Locale:                 {system_info['locale']}",
        f"Timezone:               {system_info['timezone']}",
        "",
        "NETWORK INFORMATION",
        "-" * 80,
        f"Local IP:               {network_info['local_ip']}",
        f"DNS Servers:            {network_info['dns_servers']}",
        f"Proxy:                  {network_info['proxy']}",
        "",
        "OFFICE INTEGRATION",
        "-" * 80,
        f"Microsoft Office:       {'Available' if env_status.office.available else 'Not available'}",
    ]

    if env_status.office.available:
        lines.append(f"  Version:              {env_status.office.version or 'Unknown'}")
        if env_status.office.path:
            lines.append(f"  Path:                 {env_status.office.path}")
    else:
        lines.append(f"  Reason:               {env_status.office.message or 'Not installed'}")

    lines.extend([
        f"LibreOffice:            {'Available' if env_status.libreoffice.available else 'Not available'}",
    ])

    if env_status.libreoffice.available:
        lines.append(f"  Version:              {env_status.libreoffice.version or 'Unknown'}")
        if env_status.libreoffice.path:
            lines.append(f"  Path:                 {env_status.libreoffice.path}")

    lines.extend([
        f"AWB Editor:             {'Available' if env_status.awb_editor.available else 'Not configured'}",
        "",
        "PATHS & CONFIGURATION",
        "-" * 80,
        f"Database:               {context.get_path('database')}",
        f"Logs:                   {context.get_path('logs_dir')}",
        f"Output:                 {context.get_path('output_dir')}",
        f"Templates:              {context.get_path('templates_dir')}",
        f"Config Override:        {context.user_dir / 'config_override.yaml' if context.user_dir else 'N/A'}",
        "",
        "DATABASE STATISTICS",
        "-" * 80,
        f"Database Size:          {db_stats.get('size_mb', 0)} MB",
        f"Schema Version:         {db_stats.get('schema_version', 0)}",
        f"Shipments:              {db_stats.get('shipments_count', 0)} records",
        f"Documents:              {db_stats.get('documents_count', 0)} records",
        f"Parties:                {db_stats.get('parties_count', 0)} records",
        f"Last Backup:            {db_stats.get('last_backup', 'Never')}",
        "",
        "RECENT ERRORS (Last 20)",
        "-" * 80,
    ])

    if logs['errors']:
        lines.extend(logs['errors'])
    else:
        lines.append("No recent errors")

    lines.extend([
        "",
        "RECENT WARNINGS (Last 10)",
        "-" * 80,
    ])

    if logs['warnings']:
        lines.extend(logs['warnings'])
    else:
        lines.append("No recent warnings")

    lines.extend([
        "",
        "INSTALLED PACKAGES",
        "-" * 80,
    ])

    for pkg, version in packages.items():
        if pkg != 'python':
            lines.append(f"{pkg:20} {version}")

    lines.extend([
        "",
        "=" * 80,
        "END OF DIAGNOSTIC REPORT",
        "=" * 80,
    ])

    return "\n".join(lines)
