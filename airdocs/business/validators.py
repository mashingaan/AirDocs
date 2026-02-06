# AirDocs - Validators
# ===========================

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from core.constants import (
    AWB_NUMBER_PATTERN,
    INN_PATTERN,
    KPP_PATTERN,
    EMAIL_PATTERN,
)
from core.exceptions import ValidationError
from data.models import Shipment, Party


@dataclass
class ValidationResult:
    """Result of validation operation."""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    field_errors: dict[str, str] = field(default_factory=dict)

    def add_error(self, message: str, field_name: str | None = None) -> None:
        """Add an error to the result."""
        self.is_valid = False
        self.errors.append(message)
        if field_name:
            self.field_errors[field_name] = message

    def merge(self, other: "ValidationResult") -> None:
        """Merge another validation result into this one."""
        if not other.is_valid:
            self.is_valid = False
            self.errors.extend(other.errors)
            self.field_errors.update(other.field_errors)


def validate_awb_number(awb_number: str | None) -> ValidationResult:
    """
    Validate AWB number format.

    Valid formats:
    - 8-11 digits: 12345678, 12345678901
    - IATA format: 123-12345678

    Args:
        awb_number: AWB number to validate

    Returns:
        ValidationResult
    """
    result = ValidationResult()

    if not awb_number:
        result.add_error("Номер AWB обязателен", "awb_number")
        return result

    # Remove spaces and dashes for length check
    clean_number = awb_number.replace(" ", "").replace("-", "")

    if not re.match(AWB_NUMBER_PATTERN, awb_number):
        result.add_error(
            "Неверный формат номера AWB. Ожидается 8-11 цифр или формат XXX-XXXXXXXX",
            "awb_number",
        )

    return result


def validate_inn(inn: str | None, required: bool = False) -> ValidationResult:
    """
    Validate Russian INN (ИНН).

    Valid formats:
    - 10 digits for legal entities
    - 12 digits for individuals

    Args:
        inn: INN to validate
        required: Whether INN is required

    Returns:
        ValidationResult
    """
    result = ValidationResult()

    if not inn:
        if required:
            result.add_error("ИНН обязателен", "inn")
        return result

    # Remove spaces
    inn = inn.strip()

    if not re.match(INN_PATTERN, inn):
        result.add_error(
            "Неверный формат ИНН. Ожидается 10 или 12 цифр",
            "inn",
        )
        return result

    # Checksum validation for 10-digit INN (legal entities)
    if len(inn) == 10:
        coefficients = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        checksum = sum(int(inn[i]) * coefficients[i] for i in range(9)) % 11 % 10
        if checksum != int(inn[9]):
            result.add_error("Неверная контрольная сумма ИНН", "inn")

    # Checksum validation for 12-digit INN (individuals)
    elif len(inn) == 12:
        coefficients1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        coefficients2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        checksum1 = sum(int(inn[i]) * coefficients1[i] for i in range(10)) % 11 % 10
        checksum2 = sum(int(inn[i]) * coefficients2[i] for i in range(11)) % 11 % 10
        if checksum1 != int(inn[10]) or checksum2 != int(inn[11]):
            result.add_error("Неверная контрольная сумма ИНН", "inn")

    return result


def validate_kpp(kpp: str | None, required: bool = False) -> ValidationResult:
    """
    Validate Russian KPP (КПП).

    Valid format: 9 digits

    Args:
        kpp: KPP to validate
        required: Whether KPP is required

    Returns:
        ValidationResult
    """
    result = ValidationResult()

    if not kpp:
        if required:
            result.add_error("КПП обязателен", "kpp")
        return result

    kpp = kpp.strip()

    if not re.match(KPP_PATTERN, kpp):
        result.add_error("Неверный формат КПП. Ожидается 9 цифр", "kpp")

    return result


def validate_email(email: str | None, required: bool = False) -> ValidationResult:
    """
    Validate email address.

    Args:
        email: Email to validate
        required: Whether email is required

    Returns:
        ValidationResult
    """
    result = ValidationResult()

    if not email:
        if required:
            result.add_error("Email обязателен", "email")
        return result

    email = email.strip()

    if not re.match(EMAIL_PATTERN, email):
        result.add_error("Неверный формат email", "email")

    return result


def validate_weight(weight: float | None, required: bool = True) -> ValidationResult:
    """Validate weight value."""
    result = ValidationResult()

    if weight is None:
        if required:
            result.add_error("Вес обязателен", "weight_kg")
        return result

    if weight <= 0:
        result.add_error("Вес должен быть больше 0", "weight_kg")
    elif weight > 999999.999:
        result.add_error("Вес превышает максимально допустимое значение", "weight_kg")

    return result


def validate_pieces(pieces: int | None, required: bool = True) -> ValidationResult:
    """Validate pieces count."""
    result = ValidationResult()

    if pieces is None:
        if required:
            result.add_error("Количество мест обязательно", "pieces")
        return result

    if pieces < 1:
        result.add_error("Количество мест должно быть не менее 1", "pieces")
    elif pieces > 99999:
        result.add_error("Количество мест превышает максимально допустимое значение", "pieces")

    return result


def validate_date(
    date_value: date | str | None,
    field_name: str = "date",
    required: bool = True,
    allow_future: bool = True,
    allow_past: bool = True,
) -> ValidationResult:
    """Validate a date value."""
    result = ValidationResult()

    if date_value is None:
        if required:
            result.add_error(f"Дата обязательна", field_name)
        return result

    # Parse string date if needed
    if isinstance(date_value, str):
        try:
            date_value = date.fromisoformat(date_value)
        except ValueError:
            result.add_error(f"Неверный формат даты", field_name)
            return result

    today = date.today()

    if not allow_future and date_value > today:
        result.add_error(f"Дата не может быть в будущем", field_name)

    if not allow_past and date_value < today:
        result.add_error(f"Дата не может быть в прошлом", field_name)

    return result


def validate_shipment(shipment: Shipment) -> ValidationResult:
    """
    Validate a complete shipment.

    Args:
        shipment: Shipment to validate

    Returns:
        ValidationResult with all validation errors
    """
    result = ValidationResult()

    # AWB number
    result.merge(validate_awb_number(shipment.awb_number))

    # Date
    result.merge(validate_date(shipment.shipment_date, "shipment_date"))

    # Weight
    result.merge(validate_weight(shipment.weight_kg))

    # Pieces
    result.merge(validate_pieces(shipment.pieces))

    # Volume (optional, but must be positive if provided)
    if shipment.volume_m3 is not None:
        if shipment.volume_m3 <= 0:
            result.add_error("Объем должен быть больше 0", "volume_m3")
        elif shipment.volume_m3 > 9999.999:
            result.add_error("Объем превышает максимально допустимое значение", "volume_m3")

    # Shipper ID
    if not shipment.shipper_id:
        result.add_error("Отправитель обязателен", "shipper_id")

    # Consignee ID
    if not shipment.consignee_id:
        result.add_error("Получатель обязателен", "consignee_id")

    # Goods description length
    if shipment.goods_description and len(shipment.goods_description) > 500:
        result.add_error(
            "Описание товара превышает 500 символов",
            "goods_description",
        )

    return result


def validate_party(party: Party) -> ValidationResult:
    """
    Validate a party (контрагент).

    Args:
        party: Party to validate

    Returns:
        ValidationResult with all validation errors
    """
    result = ValidationResult()

    # Name is required
    if not party.name or not party.name.strip():
        result.add_error("Наименование обязательно", "name")
    elif len(party.name) > 200:
        result.add_error("Наименование превышает 200 символов", "name")

    # Address length
    if party.address and len(party.address) > 300:
        result.add_error("Адрес превышает 300 символов", "address")

    # INN validation (optional but must be valid if provided)
    if party.inn:
        result.merge(validate_inn(party.inn))

    # KPP validation (optional but must be valid if provided)
    if party.kpp:
        result.merge(validate_kpp(party.kpp))

    # Email validation (optional but must be valid if provided)
    if party.email:
        result.merge(validate_email(party.email))

    return result


def validate_field(
    value: Any,
    field_config: dict[str, Any],
) -> ValidationResult:
    """
    Validate a single field value against its configuration from field_mapping.yaml.

    Args:
        value: Value to validate
        field_config: Field configuration from canonical mapping

    Returns:
        ValidationResult
    """
    result = ValidationResult()

    field_type = field_config.get("type", "string")
    required = field_config.get("required", False)
    validation = field_config.get("validation", {})
    ui_label = field_config.get("ui_label", "Поле")

    # Required check
    if required and (value is None or value == ""):
        result.add_error(f"{ui_label} обязателен")
        return result

    # Skip further validation if value is empty and not required
    if value is None or value == "":
        return result

    # Type-specific validation
    if field_type == "string":
        if not isinstance(value, str):
            value = str(value)

        # Pattern validation
        if "pattern" in validation:
            if not re.match(validation["pattern"], value):
                result.add_error(f"{ui_label}: неверный формат")

        # Length validation
        min_length = validation.get("min_length")
        max_length = validation.get("max_length")

        if min_length and len(value) < min_length:
            result.add_error(f"{ui_label} должен содержать минимум {min_length} символов")

        if max_length and len(value) > max_length:
            result.add_error(f"{ui_label} не должен превышать {max_length} символов")

    elif field_type == "integer":
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            result.add_error(f"{ui_label} должен быть целым числом")
            return result

        min_val = validation.get("min")
        max_val = validation.get("max")

        if min_val is not None and int_value < min_val:
            result.add_error(f"{ui_label} должен быть не менее {min_val}")

        if max_val is not None and int_value > max_val:
            result.add_error(f"{ui_label} не должен превышать {max_val}")

    elif field_type == "float":
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            result.add_error(f"{ui_label} должен быть числом")
            return result

        min_val = validation.get("min")
        max_val = validation.get("max")

        if min_val is not None and float_value < min_val:
            result.add_error(f"{ui_label} должен быть не менее {min_val}")

        if max_val is not None and float_value > max_val:
            result.add_error(f"{ui_label} не должен превышать {max_val}")

    elif field_type == "date":
        if isinstance(value, str):
            try:
                date.fromisoformat(value)
            except ValueError:
                result.add_error(f"{ui_label}: неверный формат даты")

    return result
