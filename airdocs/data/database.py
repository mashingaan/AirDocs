# AirDocs - Database Manager
# ==================================

import logging
import sys
import shutil
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Literal

from core.exceptions import DatabaseError

logger = logging.getLogger("airdocs.data")


@dataclass
class ValidationResult:
    """Result of migration validation."""
    success: bool
    error: str | None = None


@dataclass
class DatabaseStats:
    """Database statistics."""
    db_path: Path
    db_size_bytes: int
    schema_version: int | None
    total_tables: int
    table_counts: dict[str, int]
    last_migration: str | None
    is_healthy: bool
    error_message: str | None = None
    integrity_checked: bool = False
    integrity_ok: bool | None = None
    integrity_errors: list[str] = field(default_factory=list)


class Database:
    """
    SQLite database connection manager with migration support.

    Thread-safe singleton pattern for database access.
    """

    _instance: "Database | None" = None
    _initialized: bool = False

    def __new__(cls) -> "Database":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if Database._initialized:
            return
        Database._initialized = True

        self._db_path: Path | None = None
        self._connection: sqlite3.Connection | None = None
        self._migrations_path: Path | None = None
        self._last_integrity_ok: bool | None = None
        self._last_integrity_errors: list[str] = []

    def initialize(self, db_path: Path | str, migrations_path: Path | str | None = None) -> None:
        """
        Initialize database connection and run migrations.

        Args:
            db_path: Path to SQLite database file
            migrations_path: Path to migrations directory (optional)
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        if migrations_path:
            self._migrations_path = Path(migrations_path)
        else:
            # Default to data/migrations relative to this file
            self._migrations_path = Path(__file__).parent / "migrations"

        # Create connection with row factory for dict-like access
        self._connection = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,  # Allow multi-thread access
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        self._connection.row_factory = sqlite3.Row

        # Enable foreign keys
        self._connection.execute("PRAGMA foreign_keys = ON")

        # Run migrations
        self._run_migrations()

        logger.info(f"Database initialized: {self._db_path}")

    def _run_migrations(self) -> None:
        """Run all pending SQL migrations with validation and backup."""
        if not self._migrations_path or not self._migrations_path.exists():
            logger.error(
                f"Migrations path invalid or missing: {self._migrations_path}\n"
                f"  Exists: {self._migrations_path.exists() if self._migrations_path else 'N/A'}\n"
                f"  Frozen: {getattr(sys, 'frozen', False)}\n"
                f"  sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}\n"
                f"  DB path: {self._db_path}"
            )
            return

        # Get migration files sorted by name (000_, 001_, etc.)
        migration_files = sorted(self._migrations_path.glob("*.sql"))

        if not migration_files:
            logger.warning("No migration files found")
            logger.error(
                f"No migration files found in {self._migrations_path}\n"
                f"  Directory contents: "
                f"{list(self._migrations_path.iterdir()) if self._migrations_path.exists() else 'N/A'}"
            )
            return

        logger.info(f"Found {len(migration_files)} migration files in {self._migrations_path}")

        cursor = self._connection.cursor()

        # First, ensure schema_version table exists
        schema_version_file = self._migrations_path / "000_schema_version.sql"
        if schema_version_file.exists():
            sql = schema_version_file.read_text(encoding="utf-8")
            cursor.executescript(sql)
            self._connection.commit()

        # Get applied migrations
        try:
            cursor.execute("SELECT version FROM schema_version")
            applied_versions = {row[0] for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            applied_versions = set()

        # Determine pending migrations
        pending_migrations = []
        for migration_file in migration_files:
            try:
                version = int(migration_file.stem.split("_")[0])
            except (ValueError, IndexError):
                logger.warning(f"Invalid migration filename: {migration_file.name}")
                continue

            if version in applied_versions or version == 0:
                continue

            pending_migrations.append((version, migration_file))

        # If no pending migrations, return early
        if not pending_migrations:
            return

        # Validate before applying migrations
        validation = self._validate_before_migration()
        if not validation.success:
            raise DatabaseError(validation.error, operation="migrate")

        logger.info(f"Pre-migration validation passed. Pending migrations: {len(pending_migrations)}")

        # Create backup before applying migrations (only if database has data)
        backup_path = None
        if self._db_path and self._db_path.exists() and self._db_path.stat().st_size > 0:
            try:
                backup_path = self._create_database_backup()
                if backup_path:
                    logger.info(f"Database backup created: {backup_path}")
            except Exception as e:
                logger.warning(f"Failed to create backup before migration: {e}")

        # Apply pending migrations
        for version, migration_file in pending_migrations:
            try:
                sql = migration_file.read_text(encoding="utf-8")
                logger.info(
                    f"Applying migration {version}: {migration_file.name} ({len(sql)} chars)"
                )
                cursor.executescript(sql)

                # Record migration
                cursor.execute(
                    "INSERT INTO schema_version (version, name) VALUES (?, ?)",
                    (version, migration_file.stem),
                )
                self._connection.commit()
                logger.info(f"Migration applied: {migration_file.name}")

            except sqlite3.Error as e:
                self._connection.rollback()
                error_msg = (
                    f"Ошибка при применении миграции {migration_file.name}:\n"
                    f"  Версия: {version}\n"
                    f"  Путь: {migration_file}\n"
                    f"  База данных: {self._db_path}\n"
                )
                if backup_path:
                    error_msg += f"  Резервная копия: {backup_path}\n"
                error_msg += f"  Ошибка: {e}"

                logger.error(error_msg, exc_info=True)
                # Log migration file content for debugging
                try:
                    logger.error(
                        "Failed migration SQL preview (first 500 chars):\n"
                        f"{sql[:500]}"
                    )
                except Exception:
                    pass
                try:
                    raise DatabaseError(error_msg, operation="migrate", cause=e)
                except TypeError:
                    raise DatabaseError(error_msg) from e

    def _validate_before_migration(self) -> ValidationResult:
        """
        Validate database state before applying migrations.

        Checks:
        - Disk space availability
        - Database lock status
        - Migration file validity
        """
        if not self._db_path or not self._db_path.exists():
            return ValidationResult(True, None)

        # Check disk space
        try:
            db_size = self._db_path.stat().st_size
            free_space = shutil.disk_usage(self._db_path.parent).free
            required_space = 2 * db_size  # For backup and operations
            logger.debug(
                f"Disk space check: DB size={db_size / 1024 / 1024:.1f} MB, "
                f"Free space={free_space / 1024 / 1024:.1f} MB, "
                f"Required={required_space / 1024 / 1024:.1f} MB"
            )

            if free_space < required_space:
                return ValidationResult(
                    False,
                    f"Недостаточно места на диске. Требуется: {required_space / 1024 / 1024:.1f} MB, "
                    f"доступно: {free_space / 1024 / 1024:.1f} MB"
                )
        except OSError as e:
            logger.warning(f"Failed to check disk space: {e}")

        # Check for database lock
        lock_file = self._db_path.with_suffix(".db-lock")
        if lock_file.exists():
            return ValidationResult(
                False,
                "База данных используется другим процессом"
            )

        # Validate migration files
        if self._migrations_path and self._migrations_path.exists():
            migration_files = list(self._migrations_path.glob("*.sql"))
            for migration_file in migration_files:
                try:
                    content = migration_file.read_text(encoding="utf-8")
                    if not content.strip():
                        return ValidationResult(
                            False,
                            f"Ошибка чтения файла миграции: {migration_file.name} пуст"
                        )
                except OSError as e:
                    return ValidationResult(
                        False,
                        f"Ошибка чтения файла миграции: {migration_file.name}"
                    )
            logger.debug(f"Validated {len(migration_files)} migration files")

        return ValidationResult(True, None)

    def _create_database_backup(self) -> Path:
        """
        Create a backup of the database before migration.

        Returns:
            Path to the backup file
        """
        from core.app_context import get_context

        context = get_context()
        user_dir = context.user_dir if context.user_dir else self._db_path.parent

        backup_dir = user_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"airdocs_backup_{timestamp}.db"
        backup_path = backup_dir / backup_name

        shutil.copy2(self._db_path, backup_path)
        logger.info(f"Database backup created: {backup_path}")

        return backup_path

    def _apply_single_migration(self, migration_file: Path, version: int) -> None:
        """
        Apply a single migration file.

        Args:
            migration_file: Path to the migration SQL file
            version: Migration version number
        """
        sql = migration_file.read_text(encoding="utf-8")
        cursor = self._connection.cursor()

        try:
            cursor.executescript(sql)
            cursor.execute(
                "INSERT INTO schema_version (version, name) VALUES (?, ?)",
                (version, migration_file.stem),
            )
            self._connection.commit()
            logger.info(f"Migration applied: {migration_file.name}")
        except sqlite3.Error as e:
            self._connection.rollback()
            raise e
        finally:
            cursor.close()

    def needs_upgrade(self) -> bool:
        """Check if database needs migration upgrade."""
        if not self._migrations_path or not self._migrations_path.exists():
            return False

        # Get applied migrations
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT version FROM schema_version")
            applied_versions = {row[0] for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            return True

        # Check for pending migrations
        for migration_file in self._migrations_path.glob("*.sql"):
            try:
                version = int(migration_file.stem.split("_")[0])
                if version > 0 and version not in applied_versions:
                    return True
            except (ValueError, IndexError):
                continue

        return False

    def get_pending_migrations(self) -> list[tuple[int, Path]]:
        """
        Get list of pending migrations.

        Returns:
            List of (version, path) tuples for pending migrations
        """
        pending = []

        if not self._migrations_path or not self._migrations_path.exists():
            return pending

        # Get applied migrations
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT version FROM schema_version")
            applied_versions = {row[0] for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            applied_versions = set()

        # Find pending migrations
        for migration_file in sorted(self._migrations_path.glob("*.sql")):
            try:
                version = int(migration_file.stem.split("_")[0])
                if version > 0 and version not in applied_versions:
                    pending.append((version, migration_file))
            except (ValueError, IndexError):
                continue

        return pending

    def get_database_stats(
        self,
        mode: Literal["fast", "full"] = "full",
        include_integrity: bool = False,
    ) -> DatabaseStats:
        """Get database statistics."""
        db_path = self._db_path if self._db_path else Path("")
        table_counts: dict[str, int] = {}
        schema_version: int | None = None
        last_migration: str | None = None
        is_healthy = True
        error_message: str | None = None
        total_tables = 0
        db_size_bytes = 0
        integrity_checked = self._last_integrity_ok is not None
        integrity_ok = self._last_integrity_ok
        integrity_errors = list(self._last_integrity_errors)

        try:
            if self._db_path and self._db_path.exists():
                try:
                    db_size_bytes = self._db_path.stat().st_size
                except Exception as e:
                    logger.warning(f"Failed to read database size: {e}")

            try:
                table_rows = self.fetch_all(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
                table_names = {row["name"] for row in table_rows}
                total_tables = len(table_names)
            except Exception as e:
                logger.warning(f"Failed to fetch table list: {e}")
                table_names = set()
                total_tables = 0

            if "schema_version" in table_names:
                try:
                    schema_columns = self.fetch_all("PRAGMA table_info(schema_version)")
                    schema_column_names = {row["name"] for row in schema_columns}

                    if "version" in schema_column_names:
                        version_row = self.fetch_one(
                            "SELECT MAX(version) as schema_version FROM schema_version"
                        )
                        if version_row and version_row["schema_version"] is not None:
                            schema_version = int(version_row["schema_version"])

                        if "name" in schema_column_names:
                            last_row = self.fetch_one(
                                "SELECT name FROM schema_version "
                                "ORDER BY version DESC LIMIT 1"
                            )
                            if last_row and last_row["name"] is not None:
                                last_migration = str(last_row["name"])
                        else:
                            last_row = self.fetch_one(
                                "SELECT version FROM schema_version "
                                "ORDER BY version DESC LIMIT 1"
                            )
                            if last_row and last_row["version"] is not None:
                                last_migration = str(last_row["version"])
                except Exception as e:
                    logger.warning(
                        f"Failed to read schema_version metadata: {e}",
                        exc_info=True,
                    )

            if mode == "fast":
                if "shipments" in table_names:
                    try:
                        row = self.fetch_one("SELECT COUNT(*) as count FROM shipments")
                        table_counts["shipments"] = row["count"] if row else 0
                    except Exception as e:
                        logger.warning(f"Failed to count shipments: {e}")
                        table_counts["shipments"] = 0

                if "parties" in table_names:
                    try:
                        row = self.fetch_one(
                            "SELECT COUNT(*) as count FROM parties WHERE is_active = 1"
                        )
                        table_counts["parties"] = row["count"] if row else 0
                    except Exception as e:
                        logger.warning(f"Failed to count parties: {e}")
                        table_counts["parties"] = 0

                if "templates" in table_names:
                    try:
                        row = self.fetch_one(
                            "SELECT COUNT(*) as count FROM templates WHERE is_active = 1"
                        )
                        table_counts["templates"] = row["count"] if row else 0
                    except Exception as e:
                        logger.warning(f"Failed to count templates: {e}")
                        table_counts["templates"] = 0
            else:
                full_table_queries = {
                    "parties": "SELECT COUNT(*) as count FROM parties WHERE is_active = 1",
                    "templates": "SELECT COUNT(*) as count FROM templates WHERE is_active = 1",
                    "shipments": "SELECT COUNT(*) as count FROM shipments",
                    "documents": "SELECT COUNT(*) as count FROM documents",
                    "email_drafts": "SELECT COUNT(*) as count FROM email_drafts",
                    "audit_log": "SELECT COUNT(*) as count FROM audit_log",
                    "awb_overlay_calibration": "SELECT COUNT(*) as count FROM awb_overlay_calibration",
                    "environment_diagnostics": "SELECT COUNT(*) as count FROM environment_diagnostics",
                    "first_run_info": "SELECT COUNT(*) as count FROM first_run_info",
                }

                for table_name, sql in full_table_queries.items():
                    if table_name in table_names:
                        try:
                            row = self.fetch_one(sql)
                            table_counts[table_name] = row["count"] if row else 0
                        except Exception as e:
                            logger.warning(f"Failed to count {table_name}: {e}")
                            table_counts[table_name] = 0
                    else:
                        table_counts[table_name] = 0

            if mode == "full" and include_integrity:
                integrity_ok, integrity_errors = self.check_integrity()
                integrity_checked = True

            if integrity_checked and integrity_ok is False:
                is_healthy = False
                if integrity_errors and not error_message:
                    error_message = "; ".join(integrity_errors)

        except Exception as e:
            is_healthy = False
            error_message = f"Database stats collection failed: {str(e)}"
            logger.error(error_message, exc_info=True)

        return DatabaseStats(
            db_path=db_path,
            db_size_bytes=db_size_bytes,
            schema_version=schema_version,
            total_tables=total_tables,
            table_counts=table_counts,
            last_migration=last_migration,
            is_healthy=is_healthy,
            error_message=error_message,
            integrity_checked=integrity_checked,
            integrity_ok=integrity_ok,
            integrity_errors=integrity_errors,
        )

    def check_integrity(self) -> tuple[bool, list[str]]:
        """Check database integrity."""
        errors: list[str] = []

        try:
            integrity_row = self.fetch_one("PRAGMA integrity_check")
            if integrity_row:
                integrity_value = integrity_row[0]
                if str(integrity_value).lower() != "ok":
                    errors.append(str(integrity_value))

            fk_rows = self.fetch_all("PRAGMA foreign_key_check")
            for row in fk_rows:
                table_name = row["table"] if "table" in row.keys() else "unknown_table"
                rowid = row["rowid"] if "rowid" in row.keys() else "unknown_rowid"
                parent = row["parent"] if "parent" in row.keys() else "unknown_parent"
                fkid = row["fkid"] if "fkid" in row.keys() else "unknown_fkid"
                errors.append(
                    f"Foreign key check failed: table={table_name}, "
                    f"rowid={rowid}, parent={parent}, fkid={fkid}"
                )
        except Exception as e:
            logger.error(f"Integrity check failed: {e}", exc_info=True)
            errors.append(str(e))

        is_ok = len(errors) == 0
        self._last_integrity_ok = is_ok
        self._last_integrity_errors = list(errors)
        return is_ok, errors

    def apply_pending_migrations(self) -> Path | None:
        """
        Apply all pending migrations with backup.

        Returns:
            Path to backup if created, None otherwise
        """
        pending = self.get_pending_migrations()
        if not pending:
            return None

        # Validate before migration
        validation = self._validate_before_migration()
        if not validation.success:
            raise DatabaseError(validation.error, operation="migrate")

        # Create backup
        backup_path = self._create_database_backup()

        # Apply migrations
        try:
            for version, migration_file in pending:
                self._apply_single_migration(migration_file, version)
        except Exception as e:
            raise DatabaseError(
                f"Migration failed. Backup saved at: {backup_path}",
                operation="migrate",
                cause=e,
            )

        return backup_path

    @property
    def connection(self) -> sqlite3.Connection:
        """Get the database connection."""
        if self._connection is None:
            raise DatabaseError("Database not initialized", operation="get_connection")
        return self._connection

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        Context manager for database transactions.

        Usage:
            with db.transaction() as cursor:
                cursor.execute(...)
        """
        cursor = self.connection.cursor()
        try:
            yield cursor
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            raise DatabaseError(
                f"Transaction failed: {e}",
                operation="transaction",
                cause=e if isinstance(e, Exception) else None,
            )
        finally:
            cursor.close()

    def execute(
        self,
        sql: str,
        params: tuple | dict | None = None,
    ) -> sqlite3.Cursor:
        """
        Execute a SQL statement.

        Args:
            sql: SQL statement
            params: Parameters for the statement

        Returns:
            Cursor with results
        """
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return cursor
        except sqlite3.Error as e:
            raise DatabaseError(
                f"SQL execution failed: {e}",
                operation="execute",
                cause=e,
            )

    def execute_many(
        self,
        sql: str,
        params_list: list[tuple | dict],
    ) -> sqlite3.Cursor:
        """Execute a SQL statement with multiple parameter sets."""
        try:
            cursor = self.connection.cursor()
            cursor.executemany(sql, params_list)
            return cursor
        except sqlite3.Error as e:
            raise DatabaseError(
                f"SQL executemany failed: {e}",
                operation="execute_many",
                cause=e,
            )

    def fetch_one(
        self,
        sql: str,
        params: tuple | dict | None = None,
    ) -> sqlite3.Row | None:
        """Execute SQL and fetch one row."""
        cursor = self.execute(sql, params)
        return cursor.fetchone()

    def fetch_all(
        self,
        sql: str,
        params: tuple | dict | None = None,
    ) -> list[sqlite3.Row]:
        """Execute SQL and fetch all rows."""
        cursor = self.execute(sql, params)
        return cursor.fetchall()

    def insert(
        self,
        table: str,
        data: dict[str, Any],
    ) -> int:
        """
        Insert a row into a table.

        Args:
            table: Table name
            data: Dictionary of column -> value

        Returns:
            ID of inserted row
        """
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" * len(data))
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        try:
            with self.transaction() as cursor:
                cursor.execute(sql, tuple(data.values()))
                return cursor.lastrowid
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                f"Insert failed: {e}",
                operation="insert",
                table=table,
                cause=e if isinstance(e, Exception) else None,
            )

    def update(
        self,
        table: str,
        data: dict[str, Any],
        where: str,
        where_params: tuple | None = None,
    ) -> int:
        """
        Update rows in a table.

        Args:
            table: Table name
            data: Dictionary of column -> value to update
            where: WHERE clause (without 'WHERE' keyword)
            where_params: Parameters for WHERE clause

        Returns:
            Number of affected rows
        """
        set_clause = ", ".join(f"{k} = ?" for k in data.keys())
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        params = tuple(data.values()) + (where_params or ())

        try:
            with self.transaction() as cursor:
                cursor.execute(sql, params)
                return cursor.rowcount
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                f"Update failed: {e}",
                operation="update",
                table=table,
                cause=e if isinstance(e, Exception) else None,
            )

    def delete(
        self,
        table: str,
        where: str,
        where_params: tuple | None = None,
    ) -> int:
        """
        Delete rows from a table.

        Args:
            table: Table name
            where: WHERE clause (without 'WHERE' keyword)
            where_params: Parameters for WHERE clause

        Returns:
            Number of deleted rows
        """
        sql = f"DELETE FROM {table} WHERE {where}"

        try:
            with self.transaction() as cursor:
                cursor.execute(sql, where_params or ())
                return cursor.rowcount
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                f"Delete failed: {e}",
                operation="delete",
                table=table,
                cause=e if isinstance(e, Exception) else None,
            )

    def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")


# Global convenience function
def get_db() -> Database:
    """Get the global Database instance."""
    return Database()
