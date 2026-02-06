# AirDocs - Party Edit Dialog
# ===================================

import logging

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QDialogButtonBox,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QGroupBox,
)
from PySide6.QtCore import Qt

from core.constants import PartyType
from core.exceptions import ValidationError
from data.models import Party
from data.repositories import PartyRepository
from business.validators import validate_party

logger = logging.getLogger("airdocs.ui")


class PartyEditDialog(QDialog):
    """
    Dialog for creating/editing a party (контрагент).
    """

    def __init__(
        self,
        party: Party | None = None,
        party_type: PartyType | None = None,
        parent=None
    ):
        super().__init__(parent)

        self._party_repo = PartyRepository()
        self._party = party
        self._default_party_type = party_type

        self._init_ui()

        if party:
            self._load_party(party)

    def _init_ui(self):
        """Initialize dialog UI."""
        self.setWindowTitle(
            "Редактирование контрагента" if self._party
            else "Новый контрагент"
        )
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Form
        form_layout = QFormLayout()

        self.party_type = QComboBox()
        for pt in PartyType:
            self.party_type.addItem(pt.label, pt)
        form_layout.addRow("Тип:", self.party_type)

        # Set default party type
        if self._default_party_type:
            index = self.party_type.findData(self._default_party_type)
            if index >= 0:
                self.party_type.setCurrentIndex(index)

        self.name = QLineEdit()
        self.name.setPlaceholderText("Наименование организации")
        form_layout.addRow("Наименование*:", self.name)

        self.inn = QLineEdit()
        self.inn.setPlaceholderText("10 или 12 цифр")
        self.inn.setMaxLength(12)
        form_layout.addRow("ИНН:", self.inn)

        self.kpp = QLineEdit()
        self.kpp.setPlaceholderText("9 цифр")
        self.kpp.setMaxLength(9)
        form_layout.addRow("КПП:", self.kpp)

        self.address = QLineEdit()
        self.address.setPlaceholderText("Юридический адрес")
        form_layout.addRow("Адрес:", self.address)

        self.contact_person = QLineEdit()
        form_layout.addRow("Контактное лицо:", self.contact_person)

        self.phone = QLineEdit()
        self.phone.setPlaceholderText("+7 (XXX) XXX-XX-XX")
        form_layout.addRow("Телефон:", self.phone)

        self.email = QLineEdit()
        self.email.setPlaceholderText("email@example.com")
        form_layout.addRow("Email:", self.email)

        layout.addLayout(form_layout)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._on_save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _load_party(self, party: Party):
        """Load party data into form."""
        index = self.party_type.findData(party.party_type)
        if index >= 0:
            self.party_type.setCurrentIndex(index)

        self.name.setText(party.name or "")
        self.inn.setText(party.inn or "")
        self.kpp.setText(party.kpp or "")
        self.address.setText(party.address or "")
        self.contact_person.setText(party.contact_person or "")
        self.phone.setText(party.phone or "")
        self.email.setText(party.email or "")

    def _on_save(self):
        """Handle save button."""
        try:
            party = self._get_party_from_form()

            # Validate
            result = validate_party(party)
            if not result.is_valid:
                QMessageBox.warning(
                    self, "Ошибка валидации",
                    "\n".join(result.errors)
                )
                return

            # Save
            if self._party and self._party.id:
                party.id = self._party.id
                self._party_repo.update(party)
            else:
                party_id = self._party_repo.create(party)
                party.id = party_id

            self._party = party
            self.accept()

        except Exception as e:
            logger.error(f"Failed to save party: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")

    def _get_party_from_form(self) -> Party:
        """Create Party from form data."""
        party_type = self.party_type.currentData()

        return Party(
            party_type=party_type,
            name=self.name.text().strip(),
            inn=self.inn.text().strip() or None,
            kpp=self.kpp.text().strip() or None,
            address=self.address.text().strip() or None,
            contact_person=self.contact_person.text().strip() or None,
            phone=self.phone.text().strip() or None,
            email=self.email.text().strip() or None,
        )

    def get_party(self) -> Party | None:
        """Get the saved party."""
        return self._party


class PartyManagementDialog(QDialog):
    """
    Dialog for managing all parties (CRUD operations).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._party_repo = PartyRepository()
        self._init_ui()
        self._load_parties()

    def _init_ui(self):
        """Initialize dialog UI."""
        self.setWindowTitle("Справочник контрагентов")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

        # Filter
        filter_layout = QHBoxLayout()
        self.filter_type = QComboBox()
        self.filter_type.addItem("Все типы", None)
        for pt in PartyType:
            self.filter_type.addItem(pt.label, pt)
        self.filter_type.currentIndexChanged.connect(self._load_parties)
        filter_layout.addWidget(self.filter_type)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "ID", "Тип", "Наименование", "ИНН", "Телефон"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.doubleClicked.connect(self._on_edit)
        layout.addWidget(self.table)

        # Buttons
        buttons_layout = QHBoxLayout()

        btn_add = QPushButton("Добавить")
        btn_add.clicked.connect(self._on_add)
        buttons_layout.addWidget(btn_add)

        btn_edit = QPushButton("Редактировать")
        btn_edit.clicked.connect(self._on_edit)
        buttons_layout.addWidget(btn_edit)

        btn_delete = QPushButton("Удалить")
        btn_delete.clicked.connect(self._on_delete)
        buttons_layout.addWidget(btn_delete)

        buttons_layout.addStretch()

        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        buttons_layout.addWidget(btn_close)

        layout.addLayout(buttons_layout)

    def _load_parties(self):
        """Load parties into table."""
        party_type = self.filter_type.currentData()

        try:
            parties = self._party_repo.get_all(party_type=party_type)

            self.table.setRowCount(len(parties))
            for row, party in enumerate(parties):
                self.table.setItem(row, 0, QTableWidgetItem(str(party.id)))
                self.table.setItem(row, 1, QTableWidgetItem(party.party_type.label))
                self.table.setItem(row, 2, QTableWidgetItem(party.name))
                self.table.setItem(row, 3, QTableWidgetItem(party.inn or ""))
                self.table.setItem(row, 4, QTableWidgetItem(party.phone or ""))

                self.table.item(row, 0).setData(Qt.UserRole, party.id)

        except Exception as e:
            logger.error(f"Failed to load parties: {e}")

    def _get_selected_party_id(self) -> int | None:
        """Get ID of selected party."""
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            return self.table.item(row, 0).data(Qt.UserRole)
        return None

    def _on_add(self):
        """Handle add button."""
        party_type = self.filter_type.currentData()
        dialog = PartyEditDialog(party_type=party_type, parent=self)
        if dialog.exec():
            self._load_parties()

    def _on_edit(self):
        """Handle edit button."""
        party_id = self._get_selected_party_id()
        if not party_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите контрагента")
            return

        party = self._party_repo.get_by_id(party_id)
        if party:
            dialog = PartyEditDialog(party=party, parent=self)
            if dialog.exec():
                self._load_parties()

    def _on_delete(self):
        """Handle delete button."""
        party_id = self._get_selected_party_id()
        if not party_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите контрагента")
            return

        reply = QMessageBox.question(
            self, "Подтверждение",
            "Удалить выбранного контрагента?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self._party_repo.delete(party_id)
                self._load_parties()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить: {e}")
