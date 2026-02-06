# AirDocs - Party Selector Widget
# =======================================

import logging

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QComboBox,
    QPushButton,
)
from PySide6.QtCore import Signal

from core.constants import PartyType
from data.models import Party
from data.repositories import PartyRepository

logger = logging.getLogger("airdocs.ui")


class PartySelector(QWidget):
    """
    Widget for selecting a party (контрагент) from a dropdown.

    Features:
    - Dropdown with searchable parties list
    - Button to add new party
    - Filters by party type
    """

    party_changed = Signal(int)  # Emitted when selection changes (party_id)

    def __init__(self, party_type: str = "shipper", parent=None):
        super().__init__(parent)

        self._party_type = PartyType(party_type)
        self._party_repo = PartyRepository()
        self._required = True

        self._init_ui()
        self._load_parties()

    def _init_ui(self):
        """Initialize UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Party dropdown
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        self.combo.setMinimumWidth(200)
        self.combo.currentIndexChanged.connect(self._on_selection_changed)
        layout.addWidget(self.combo, 1)

        # Add new button
        self.btn_add = QPushButton("+")
        self.btn_add.setMaximumWidth(30)
        self.btn_add.setToolTip("Добавить нового контрагента")
        self.btn_add.clicked.connect(self._on_add_clicked)
        layout.addWidget(self.btn_add)

    def _load_parties(self):
        """Load parties into dropdown."""
        self.combo.clear()

        if not self._required:
            self.combo.addItem("— Не выбрано —", None)

        try:
            parties = self._party_repo.get_all(party_type=self._party_type)
            for party in parties:
                display_text = party.name
                if party.inn:
                    display_text += f" (ИНН: {party.inn})"
                self.combo.addItem(display_text, party.id)

        except Exception as e:
            logger.error(f"Failed to load parties: {e}")

    def refresh(self):
        """Refresh parties list."""
        current_id = self.get_selected_id()
        self._load_parties()
        if current_id:
            self.set_selected_id(current_id)

    def has_parties(self) -> bool:
        """Check if there are any parties available."""
        # If not required, first item is "— Не выбрано —"
        min_count = 1 if not self._required else 0
        return self.combo.count() > min_count

    def show_empty_warning(self) -> bool:
        """
        Show warning when no parties available.
        Returns True if user added a party, False otherwise.
        """
        from PySide6.QtWidgets import QMessageBox

        party_type_label = self._party_type.label.lower()

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Нет доступных контрагентов")
        msg.setText(
            f"В базе данных нет ни одного контрагента типа '{party_type_label}'."
        )
        msg.setInformativeText("Добавьте контрагента для продолжения работы.")

        btn_add = msg.addButton("Добавить контрагента", QMessageBox.AcceptRole)
        btn_cancel = msg.addButton("Отмена", QMessageBox.RejectRole)

        msg.exec()

        if msg.clickedButton() == btn_add:
            # Open add dialog
            self._on_add_clicked()

            # IMPORTANT: after closing the add dialog, refresh/populate the combo
            # so has_parties() reflects the new state.
            self.refresh()

            # Check if party was added (after refresh)
            return self.has_parties()

        return False

    def get_selected_id(self) -> int | None:
        """Get ID of selected party (no side effects / no dialogs)."""
        return self.combo.currentData()

    def set_selected_id(self, party_id: int | None):
        """Set selected party by ID."""
        if party_id is None:
            if not self._required:
                self.combo.setCurrentIndex(0)
            return

        for i in range(self.combo.count()):
            if self.combo.itemData(i) == party_id:
                self.combo.setCurrentIndex(i)
                return

        logger.warning(f"Party ID {party_id} not found in dropdown")

    def get_selected_party(self) -> Party | None:
        """Get selected party object."""
        party_id = self.get_selected_id()
        if party_id:
            return self._party_repo.get_by_id(party_id)
        return None

    def set_required(self, required: bool):
        """Set whether selection is required."""
        self._required = required
        self._load_parties()

    def clear(self):
        """Clear selection."""
        if self._required:
            self.combo.setCurrentIndex(-1)
        else:
            self.combo.setCurrentIndex(0)

    def validate(self) -> tuple[bool, str | None]:
        """
        Validate party selection (NO modal dialogs).
        Returns (is_valid, error_message).
        """
        party_type_label = self._party_type.label.lower()

        # If there are no parties at all, just report the error.
        # Offering "Add party" should be handled explicitly on Save via ensure_parties().
        if not self.has_parties():
            return False, f"Нет доступных контрагентов типа '{party_type_label}'"

        selected_id = self.get_selected_id()

        if self._required and not selected_id:
            return False, f"Выберите {party_type_label}"

        return True, None

    def ensure_parties(self) -> bool:
        """Ensure parties exist for required selector (may show modal)."""
        if self._required and not self.has_parties():
            return self.show_empty_warning()
        return True

    def _on_selection_changed(self, index):
        """Handle selection change."""
        party_id = self.combo.itemData(index)
        self.party_changed.emit(party_id if party_id else 0)

    def _on_add_clicked(self):
        """Handle add button click."""
        from ui.dialogs.party_edit_dialog import PartyEditDialog

        dialog = PartyEditDialog(party_type=self._party_type, parent=self)
        if dialog.exec():
            # Refresh and select new party
            self.refresh()
            new_party = dialog.get_party()
            if new_party and new_party.id:
                self.set_selected_id(new_party.id)
