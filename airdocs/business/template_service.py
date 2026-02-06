# AirDocs - Template Service
# ==================================

import logging
from typing import Any

from core.exceptions import ValidationError, DatabaseError
from data.models import Template
from data.repositories import TemplateRepository, AuditLogRepository

logger = logging.getLogger("airdocs.business")


class TemplateService:
    """
    Service for managing document templates (presets).

    Handles:
    - CRUD operations for presets
    - Loading/saving preset values
    - Template versioning
    """

    def __init__(self):
        self._template_repo = TemplateRepository()
        self._audit_repo = AuditLogRepository()

    def create_preset(
        self,
        name: str,
        field_values: dict[str, Any],
        client_type: str | None = None,
        description: str | None = None,
    ) -> Template:
        """
        Create a new preset template.

        Args:
            name: Unique name for the preset
            field_values: Dictionary of field values to pre-fill
            client_type: Optional client type (TiA, FF, IP)
            description: Optional description

        Returns:
            Created Template record

        Raises:
            ValidationError: If name already exists
        """
        # Check for duplicate name
        existing = self._template_repo.get_by_name(name)
        if existing:
            raise ValidationError(
                f"Пресет с именем '{name}' уже существует",
                field="template_name",
            )

        template = Template(
            template_name=name,
            template_type="preset",
            client_type=client_type,
            description=description,
            field_values=field_values,
        )

        template_id = self._template_repo.create(template)
        template.id = template_id

        # Audit log
        self._audit_repo.log_action(
            entity_type="template",
            entity_id=template_id,
            action="created",
            new_values={"name": name, "type": "preset"},
        )

        logger.info(f"Created preset: {name} (id={template_id})")
        return template

    def update_preset(
        self,
        template_id: int,
        name: str | None = None,
        field_values: dict[str, Any] | None = None,
        client_type: str | None = None,
        description: str | None = None,
    ) -> Template:
        """
        Update an existing preset.

        Args:
            template_id: ID of preset to update
            name: New name (optional)
            field_values: New field values (optional)
            client_type: New client type (optional)
            description: New description (optional)

        Returns:
            Updated Template record
        """
        template = self._template_repo.get_by_id(template_id)
        if not template:
            raise DatabaseError(
                f"Пресет не найден (id={template_id})",
                operation="update",
                table="templates",
            )

        if template.template_type != "preset":
            raise ValidationError(
                "Можно редактировать только пресеты",
                field="template_type",
            )

        old_values = {
            "name": template.template_name,
            "field_values": template.field_values,
        }

        # Update fields
        if name is not None:
            # Check for duplicate name if changed
            if name != template.template_name:
                existing = self._template_repo.get_by_name(name)
                if existing:
                    raise ValidationError(
                        f"Пресет с именем '{name}' уже существует",
                        field="template_name",
                    )
            template.template_name = name

        if field_values is not None:
            template.field_values = field_values

        if client_type is not None:
            template.client_type = client_type

        if description is not None:
            template.description = description

        self._template_repo.update(template)

        # Audit log
        self._audit_repo.log_action(
            entity_type="template",
            entity_id=template_id,
            action="updated",
            old_values=old_values,
            new_values={
                "name": template.template_name,
                "field_values": template.field_values,
            },
        )

        logger.info(f"Updated preset: {template.template_name} (id={template_id})")
        return template

    def delete_preset(self, template_id: int) -> bool:
        """
        Delete a preset (soft delete).

        Args:
            template_id: ID of preset to delete

        Returns:
            True if deleted
        """
        template = self._template_repo.get_by_id(template_id)
        if not template:
            return False

        if template.template_type != "preset":
            raise ValidationError(
                "Можно удалять только пресеты",
                field="template_type",
            )

        result = self._template_repo.delete(template_id)

        if result:
            self._audit_repo.log_action(
                entity_type="template",
                entity_id=template_id,
                action="deleted",
                old_values={"name": template.template_name},
            )
            logger.info(f"Deleted preset: {template.template_name} (id={template_id})")

        return result

    def get_preset(self, template_id: int) -> Template | None:
        """Get preset by ID."""
        template = self._template_repo.get_by_id(template_id)
        if template and template.template_type == "preset":
            return template
        return None

    def get_preset_by_name(self, name: str) -> Template | None:
        """Get preset by name."""
        template = self._template_repo.get_by_name(name)
        if template and template.template_type == "preset":
            return template
        return None

    def list_presets(
        self,
        client_type: str | None = None,
    ) -> list[Template]:
        """
        List all presets, optionally filtered by client type.

        Args:
            client_type: Optional filter by client type

        Returns:
            List of preset Templates
        """
        return self._template_repo.get_presets(client_type)

    def apply_preset_values(
        self,
        preset_id: int,
        current_values: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Apply preset values to current form values.

        Preset values override current values where they exist.

        Args:
            preset_id: ID of preset to apply
            current_values: Current form values

        Returns:
            Merged values dictionary
        """
        preset = self.get_preset(preset_id)
        if not preset:
            return current_values

        # Merge: preset values override current
        result = current_values.copy()
        result.update(preset.field_values)

        return result

    def save_current_as_preset(
        self,
        name: str,
        current_values: dict[str, Any],
        client_type: str | None = None,
    ) -> Template:
        """
        Save current form values as a new preset.

        Args:
            name: Name for the new preset
            current_values: Current form values to save

        Returns:
            Created Template record
        """
        return self.create_preset(
            name=name,
            field_values=current_values,
            client_type=client_type,
            description=f"Создан из текущих значений формы",
        )
