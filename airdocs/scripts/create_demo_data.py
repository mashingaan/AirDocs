# AirDocs - Create Demo Data
# ===================================
# Creates sample parties and shipments for testing

import sys
from pathlib import Path
from datetime import date, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.app_context import AppContext
from data.database import Database
from data.models import Party, Shipment
from data.repositories import PartyRepository, ShipmentRepository
from core.constants import PartyType, ShipmentType, ShipmentStatus


def main():
    print("Creating demo data...")
    print("=" * 50)

    # Initialize app context and database
    app_dir = Path(__file__).parent.parent
    context = AppContext()
    context.initialize(base_path=app_dir)

    db_path = context.get_path("database")
    migrations_path = app_dir / "data" / "migrations"
    db = Database()
    db.initialize(db_path, migrations_path)

    party_repo = PartyRepository()
    shipment_repo = ShipmentRepository()

    # Create sample shippers (отправители)
    shippers = [
        Party(
            party_type=PartyType.SHIPPER,
            name="ООО 'Рога и Копыта'",
            inn="7701234567",
            kpp="770101001",
            address="г. Москва, ул. Тверская, д. 1, офис 101",
            phone="+7 (495) 123-45-67",
            email="info@rogakopyta.ru",
        ),
        Party(
            party_type=PartyType.SHIPPER,
            name="ИП Иванов И.И.",
            inn="770112345678",
            address="г. Москва, ул. Арбат, д. 10",
            phone="+7 (916) 111-22-33",
            email="ivanov@mail.ru",
        ),
        Party(
            party_type=PartyType.SHIPPER,
            name="АО 'ТехноЭкспорт'",
            inn="7702345678",
            kpp="770201001",
            address="г. Москва, Ленинградский пр-т, д. 80, стр. 5",
            phone="+7 (495) 987-65-43",
            email="export@technoexport.ru",
        ),
    ]

    # Create sample consignees (получатели)
    consignees = [
        Party(
            party_type=PartyType.CONSIGNEE,
            name="Global Imports Ltd",
            address="123 Main Street, London, UK",
            phone="+44 20 1234 5678",
            email="imports@globalimports.co.uk",
        ),
        Party(
            party_type=PartyType.CONSIGNEE,
            name="Shanghai Trade Co.",
            address="888 Nanjing Road, Shanghai, China",
            phone="+86 21 5555 6666",
            email="trade@shanghaitrade.cn",
        ),
        Party(
            party_type=PartyType.CONSIGNEE,
            name="Deutsche Logistik GmbH",
            address="Hauptstraße 100, Berlin, Germany",
            phone="+49 30 123456",
            email="info@deutschelogistik.de",
        ),
    ]

    # Create sample agents (агенты)
    agents = [
        Party(
            party_type=PartyType.AGENT,
            name="Аэрофлот Карго",
            inn="7712038150",
            address="г. Москва, аэропорт Шереметьево",
            phone="+7 (495) 223-55-55",
            email="cargo@aeroflot.ru",
        ),
        Party(
            party_type=PartyType.AGENT,
            name="S7 Cargo",
            inn="5448100656",
            address="г. Москва, аэропорт Домодедово",
            phone="+7 (495) 777-99-99",
            email="cargo@s7.ru",
        ),
    ]

    # Save parties
    shipper_ids = []
    for party in shippers:
        party_id = party_repo.create(party)
        shipper_ids.append(party_id)
        print(f"Created shipper: {party.name} (id={party_id})")

    consignee_ids = []
    for party in consignees:
        party_id = party_repo.create(party)
        consignee_ids.append(party_id)
        print(f"Created consignee: {party.name} (id={party_id})")

    agent_ids = []
    for party in agents:
        party_id = party_repo.create(party)
        agent_ids.append(party_id)
        print(f"Created agent: {party.name} (id={party_id})")

    print()

    # Create sample shipments
    shipments = [
        Shipment(
            awb_number="555-12345678",
            shipment_date=date.today(),
            shipment_type=ShipmentType.AIR,
            status=ShipmentStatus.DRAFT,
            weight_kg=150.5,
            pieces=3,
            volume_m3=0.8,
            goods_description="Электроника / Electronics",
            shipper_id=shipper_ids[0],
            consignee_id=consignee_ids[0],
            agent_id=agent_ids[0],
            notes="Тестовая отправка",
        ),
        Shipment(
            awb_number="555-87654321",
            shipment_date=date.today() - timedelta(days=1),
            shipment_type=ShipmentType.AIR,
            status=ShipmentStatus.READY,
            weight_kg=500.0,
            pieces=10,
            volume_m3=2.5,
            goods_description="Запчасти / Spare parts",
            shipper_id=shipper_ids[1],
            consignee_id=consignee_ids[1],
            agent_id=agent_ids[1],
        ),
        Shipment(
            awb_number="555-11112222",
            shipment_date=date.today() - timedelta(days=2),
            shipment_type=ShipmentType.AIR,
            status=ShipmentStatus.SENT,
            weight_kg=75.25,
            pieces=2,
            goods_description="Образцы продукции / Product samples",
            shipper_id=shipper_ids[2],
            consignee_id=consignee_ids[2],
        ),
        Shipment(
            awb_number="LOCAL-001",
            shipment_date=date.today(),
            shipment_type=ShipmentType.LOCAL_DELIVERY,
            status=ShipmentStatus.DRAFT,
            weight_kg=25.0,
            pieces=1,
            goods_description="Документы / Documents",
            shipper_id=shipper_ids[0],
            consignee_id=consignee_ids[0],
        ),
    ]

    for shipment in shipments:
        shipment_id = shipment_repo.create(shipment)
        print(f"Created shipment: {shipment.awb_number} (id={shipment_id})")

    print()
    print("=" * 50)
    print("Demo data created successfully!")
    print()
    print("You can now:")
    print("1. Open the application: python main.py")
    print("2. Go to 'Бронирование' tab to see shipments")
    print("3. Select a shipment and click 'Сформировать AWB'")


if __name__ == "__main__":
    main()
