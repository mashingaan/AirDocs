# AirDocs - Setup Wizard Dialog
# ====================================

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QWidget,
    QStackedWidget,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QSpacerItem,
    QSizePolicy,
)

from business.validators import validate_party
from core.constants import PartyType
from data.models import Party
from data.repositories import PartyRepository

logger = logging.getLogger("airdocs.ui")


class SetupWizardDialog(QDialog):
    """
    Setup Wizard Dialog for first-time application setup.

    Guides the user through initial configuration:
    1. Welcome and introduction
    2. Creating essential parties (shippers, consignees)
    3. Completion and next steps

    The wizard can be skipped (Skip) or cancelled (Cancel). Wizard outcome is persisted to the first_run_info table by handle_first_run().
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._outcome = "cancelled"

        self._init_ui()
        self._create_pages()
        self._update_buttons()

    def _init_ui(self) -> None:
        """Initialize wizard UI."""
        self.setWindowTitle("Мастер первоначальной настройки")
        self.setModal(True)
        self.setMinimumSize(760, 520)

        main_layout = QVBoxLayout(self)

        self.pages = QStackedWidget()
        main_layout.addWidget(self.pages)

        button_layout = QHBoxLayout()

        self.btn_back = QPushButton("Назад")
        self.btn_back.clicked.connect(self._prev_page)
        button_layout.addWidget(self.btn_back)

        self.btn_skip = QPushButton("Пропустить")
        self.btn_skip.clicked.connect(self._skip_wizard)
        button_layout.addWidget(self.btn_skip)

        button_layout.addItem(
            QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        self.btn_next = QPushButton("Далее")
        self.btn_next.clicked.connect(self._next_page)
        button_layout.addWidget(self.btn_next)

        self.btn_finish = QPushButton("Начать работу")
        self.btn_finish.clicked.connect(self._finish_wizard)
        button_layout.addWidget(self.btn_finish)

        main_layout.addLayout(button_layout)

    def _create_pages(self) -> None:
        """Create wizard pages."""
        self.welcome_page = WelcomePage()
        self.welcome_page.start_requested.connect(self._next_page)

        self.party_page = PartyCreationPage()
        self.party_page.skip_requested.connect(self._skip_wizard)

        self.completion_page = CompletionPage()

        self.pages.addWidget(self.welcome_page)
        self.pages.addWidget(self.party_page)
        self.pages.addWidget(self.completion_page)

    def _next_page(self) -> None:
        """Go to the next page."""
        current = self.pages.currentIndex()

        if current == 0:
            self.pages.setCurrentIndex(1)
            self._update_buttons()
            return

        if current == 1:
            if not self.party_page._validate():
                return

            created_parties = self.party_page._get_created_parties()
            self.completion_page.set_summary(
                len(created_parties["shippers"]),
                len(created_parties["consignees"]),
            )
            self.pages.setCurrentIndex(2)
            self._update_buttons()

    def _prev_page(self) -> None:
        """Go to the previous page."""
        current = self.pages.currentIndex()
        if current > 0:
            self.pages.setCurrentIndex(current - 1)
            self._update_buttons()

    def _skip_wizard(self) -> None:
        """Skip wizard setup."""
        self._outcome = "skipped"
        self.reject()

    def _finish_wizard(self) -> None:
        """Finish wizard setup."""
        self._outcome = "completed"
        self.accept()

    def _update_buttons(self) -> None:
        """Update navigation buttons visibility."""
        current = self.pages.currentIndex()

        if current == 0:
            self.btn_back.setVisible(False)
            self.btn_next.setVisible(True)
            self.btn_skip.setVisible(True)
            self.btn_finish.setVisible(False)
            return

        if current == 1:
            self.btn_back.setVisible(True)
            self.btn_next.setVisible(True)
            self.btn_skip.setVisible(True)
            self.btn_finish.setVisible(False)
            return

        self.btn_back.setVisible(False)
        self.btn_next.setVisible(False)
        self.btn_skip.setVisible(False)
        self.btn_finish.setVisible(True)

    def get_outcome(self) -> str:
        """Return wizard outcome: 'completed', 'skipped', or 'cancelled'."""
        return self._outcome


class WelcomePage(QWidget):
    """Welcome page for setup wizard."""

    start_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QLabel("<h2>📋 Добро пожаловать в AWB Dispatcher</h2>")
        header.setWordWrap(True)
        layout.addWidget(header)

        description = QLabel(
            "Мастер поможет выполнить первоначальную настройку приложения.\n\n"
            "Чтобы начать работу, рекомендуется добавить минимум одного отправителя "
            "и одного получателя."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addStretch()

        start_btn = QPushButton("Начать настройку")
        start_btn.clicked.connect(self.start_requested.emit)
        layout.addWidget(start_btn, alignment=Qt.AlignRight)


class PartyCreationPage(QWidget):
    """Page for creating initial parties."""

    skip_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._party_repo = PartyRepository()
        self._shipper_ids: list[int] = []
        self._consignee_ids: list[int] = []

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QLabel("<h2>Создание контрагентов</h2>")
        header.setWordWrap(True)
        layout.addWidget(header)

        intro = QLabel(
            "Добавьте минимум одного отправителя и одного получателя.\n"
            "Поля \"Наименование\" и \"Адрес\" обязательны."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        shipper_tab = QWidget()
        shipper_layout = QVBoxLayout(shipper_tab)
        shipper_layout.addWidget(QLabel("<b>📤 Отправители</b>"))

        shipper_form = QFormLayout()
        self.shipper_name = QLineEdit()
        self.shipper_name.setPlaceholderText("Наименование*")
        shipper_form.addRow("Наименование*:", self.shipper_name)
        self.shipper_address = QLineEdit()
        self.shipper_address.setPlaceholderText("Адрес*")
        shipper_form.addRow("Адрес*:", self.shipper_address)
        shipper_layout.addLayout(shipper_form)

        self.btn_add_shipper = QPushButton("Добавить")
        self.btn_add_shipper.clicked.connect(self._add_shipper)
        shipper_layout.addWidget(self.btn_add_shipper, alignment=Qt.AlignRight)

        self.shipper_list = QListWidget()
        shipper_layout.addWidget(self.shipper_list)

        shipper_remove_btn = QPushButton("Удалить выбранного")
        shipper_remove_btn.clicked.connect(self._remove_selected)
        shipper_layout.addWidget(shipper_remove_btn, alignment=Qt.AlignRight)

        self.tabs.addTab(shipper_tab, "Отправители")

        consignee_tab = QWidget()
        consignee_layout = QVBoxLayout(consignee_tab)
        consignee_layout.addWidget(QLabel("<b>📥 Получатели</b>"))

        consignee_form = QFormLayout()
        self.consignee_name = QLineEdit()
        self.consignee_name.setPlaceholderText("Наименование*")
        consignee_form.addRow("Наименование*:", self.consignee_name)
        self.consignee_address = QLineEdit()
        self.consignee_address.setPlaceholderText("Адрес*")
        consignee_form.addRow("Адрес*:", self.consignee_address)
        consignee_layout.addLayout(consignee_form)

        self.btn_add_consignee = QPushButton("Добавить")
        self.btn_add_consignee.clicked.connect(self._add_consignee)
        consignee_layout.addWidget(self.btn_add_consignee, alignment=Qt.AlignRight)

        self.consignee_list = QListWidget()
        consignee_layout.addWidget(self.consignee_list)

        consignee_remove_btn = QPushButton("Удалить выбранного")
        consignee_remove_btn.clicked.connect(self._remove_selected)
        consignee_layout.addWidget(consignee_remove_btn, alignment=Qt.AlignRight)

        self.tabs.addTab(consignee_tab, "Получатели")

    def _add_shipper(self) -> None:
        """Add shipper from form."""
        self._add_party(
            party_type=PartyType.SHIPPER,
            name_edit=self.shipper_name,
            address_edit=self.shipper_address,
            list_widget=self.shipper_list,
            ids=self._shipper_ids,
        )

    def _add_consignee(self) -> None:
        """Add consignee from form."""
        self._add_party(
            party_type=PartyType.CONSIGNEE,
            name_edit=self.consignee_name,
            address_edit=self.consignee_address,
            list_widget=self.consignee_list,
            ids=self._consignee_ids,
        )

    def _add_party(
        self,
        party_type: PartyType,
        name_edit: QLineEdit,
        address_edit: QLineEdit,
        list_widget: QListWidget,
        ids: list[int],
    ) -> None:
        name = name_edit.text().strip()
        address = address_edit.text().strip()

        if not name or not address:
            QMessageBox.warning(
                self,
                "Недостаточно данных",
                "Заполните обязательные поля: Наименование и Адрес.",
            )
            return

        party = Party(
            party_type=party_type,
            name=name,
            address=address,
        )

        validation = validate_party(party)
        if not validation.is_valid:
            QMessageBox.warning(
                self,
                "Ошибка валидации",
                "\n".join(validation.errors),
            )
            return

        try:
            party_id = self._party_repo.create(party)
            ids.append(party_id)

            item = QListWidgetItem(f"{party.name} — {party.address}")
            item.setData(Qt.UserRole, party_id)
            list_widget.addItem(item)

            name_edit.clear()
            address_edit.clear()
        except Exception as e:
            logger.error(
                f"Failed to create party in setup wizard: {e}",
                exc_info=True,
            )
            QMessageBox.critical(
                self,
                "Ошибка сохранения",
                f"Не удалось сохранить контрагента:\n{e}",
            )

            reply = QMessageBox.question(
                self,
                "Критическая ошибка",
                "Произошла критическая ошибка. Пропустить мастер настройки?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.skip_requested.emit()

    def _remove_selected(self) -> None:
        """Remove selected party from current tab."""
        if self.tabs.currentIndex() == 0:
            list_widget = self.shipper_list
            ids = self._shipper_ids
        else:
            list_widget = self.consignee_list
            ids = self._consignee_ids

        item = list_widget.currentItem()
        if item is None:
            QMessageBox.warning(
                self,
                "Предупреждение",
                "Выберите запись для удаления.",
            )
            return

        party_id = item.data(Qt.UserRole)
        try:
            self._party_repo.delete(party_id)
            if party_id in ids:
                ids.remove(party_id)
            list_widget.takeItem(list_widget.row(item))
        except Exception as e:
            logger.error(
                f"Failed to delete party in setup wizard: {e}",
                exc_info=True,
            )
            QMessageBox.critical(
                self,
                "Ошибка удаления",
                f"Не удалось удалить контрагента:\n{e}",
            )

    def _validate(self) -> bool:
        """Validate required initial parties."""
        if len(self._shipper_ids) < 1 or len(self._consignee_ids) < 1:
            QMessageBox.warning(
                self,
                "Настройка не завершена",
                "Добавьте минимум одного отправителя и одного получателя.",
            )
            return False

        return True

    def _get_created_parties(self) -> dict[str, list[int]]:
        """Return ids of created parties."""
        return {
            "shippers": list(self._shipper_ids),
            "consignees": list(self._consignee_ids),
        }


class CompletionPage(QWidget):
    """Completion page for setup wizard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QLabel("<h2>✅ Настройка завершена!</h2>")
        header.setWordWrap(True)
        layout.addWidget(header)

        self.summary_label = QLabel("Контрагенты успешно добавлены.")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        hint = QLabel(
            "Позже вы можете редактировать и добавлять контрагентов в разделе "
            "\"Справочник контрагентов\"."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        next_steps = QLabel(
            "<b>Следующие шаги:</b>"
            "<ul>"
            "<li>Перейти в \"Бронирование\"</li>"
            "<li>Создать первую отправку</li>"
            "<li>Сформировать AWB</li>"
            "</ul>"
        )
        next_steps.setWordWrap(True)
        layout.addWidget(next_steps)

        layout.addStretch()

    def set_summary(self, shipper_count: int, consignee_count: int) -> None:
        """Update completion summary."""
        self.summary_label.setText(
            f"Создано отправителей: {shipper_count}\n"
            f"Создано получателей: {consignee_count}"
        )

