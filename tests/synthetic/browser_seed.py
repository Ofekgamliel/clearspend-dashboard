from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from openpyxl import Workbook

from tests.synthetic.support import add_import, add_income, add_transaction, connect, create_database


def create_browser_statement() -> Path:
    path = Path(tempfile.gettempdir()) / "clearspend-browser-e2e-statement.xlsx"
    path.unlink(missing_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Synthetic Isracard"
    sheet["A1"] = "תאריך רכישה"
    sheet["C1"] = "December 2030"
    sheet["A2"] = "ישראכרט Synthetic - 0003"
    sheet["A3"] = "נכונים לתאריך 31/12/2030"
    sheet["B4"] = 'סה"כ לחיוב החודש בכרטיס'
    sheet["E4"] = "300.00"
    sheet["A5"] = "10.12.30"
    sheet["B5"] = "Synthetic Browser Import"
    sheet["C5"] = "300.00"
    sheet["D5"] = "ILS"
    sheet["E5"] = "300.00"
    sheet["F5"] = "ILS"
    sheet["G5"] = "browser-import-1"
    workbook.save(path)
    return path


def seed_database(database: Path) -> None:
    if database.name != "clearspend-browser-e2e.db":
        raise ValueError("Browser tests may only replace the dedicated synthetic database")
    database.parent.mkdir(parents=True, exist_ok=True)
    database.unlink(missing_ok=True)
    create_browser_statement()
    create_database(database)
    connection = connect(database)
    first_import = add_import(connection, name="synthetic-max-2026-11.xlsx")
    second_import = add_import(connection, name="synthetic-isracard-2026-11.xlsx")
    connection.execute(
        "UPDATE imports SET provider='max',card_last4='0001',product_name='Synthetic MAX' WHERE id=?",
        (first_import,),
    )
    connection.execute(
        "UPDATE imports SET provider='isracard',card_last4='0002',product_name='Synthetic Isracard' WHERE id=?",
        (second_import,),
    )
    rows = [
        (first_import, "max-oct-market", "Synthetic Market", 420.50, "Food & groceries", "2026-10-04", "2026-10", "max", "0001"),
        (first_import, "max-oct-cafe", "Synthetic Cafe", 86.00, "Restaurants", "2026-10-12", "2026-10", "max", "0001"),
        (first_import, "max-oct-gym", "Synthetic Gym", 199.00, "Fitness", "2026-10-15", "2026-10", "max", "0001"),
        (first_import, "max-oct-utility-north", "Synthetic Utility North", 310.00, "Utilities", "2026-10-21", "2026-10", "max", "0001"),
        (second_import, "isra-oct-transit", "Synthetic Transit", 115.00, "Transport", "2026-10-18", "2026-10", "isracard", "0002"),
        (first_import, "max-nov-market", "Synthetic Market", 510.25, "Food & groceries", "2026-11-03", "2026-11", "max", "0001"),
        (first_import, "max-nov-gym", "Synthetic Gym", 199.00, "Fitness", "2026-11-07", "2026-11", "max", "0001"),
        (first_import, "max-nov-utility-north", "Synthetic Utility North", 315.00, "Utilities", "2026-11-08", "2026-11", "max", "0001"),
        (second_import, "isra-nov-utility-south", "Synthetic Utility South", 275.00, "Utilities", "2026-11-10", "2026-11", "isracard", "0002"),
        (second_import, "isra-nov-cafe", "Synthetic Cafe", 132.40, "Restaurants", "2026-11-09", "2026-11", "isracard", "0002"),
        (second_import, "isra-nov-shop", "Synthetic Shop", 760.00, "Fashion", "2026-11-11", "2026-11", "isracard", "0002"),
    ]
    for import_id, key, merchant, amount, category, date, month, provider, last4 in rows:
        transaction_id = add_transaction(
            connection,
            import_id,
            key=key,
            merchant=merchant,
            amount=amount,
            category=category,
            transaction_date=date,
            billing_month=month,
            card_last4=last4,
        )
        connection.execute("UPDATE transactions SET provider=? WHERE id=?", (provider, transaction_id))
    for merchant, group_id, display_name, category in (
        ("synthetic utility north", "synthetic-utilities", "Synthetic Utilities", "Utilities"),
        ("synthetic utility south", "synthetic-utilities", "Synthetic Utilities", "Utilities"),
        ("synthetic gym", "synthetic-gym", "Synthetic Gym", "Fitness"),
    ):
        connection.execute(
            """INSERT INTO merchant_display_mappings(
            merchant_normalized,canonical_group_id,display_name,updated_at
            ) VALUES(?,?,?,?)""",
            (merchant, group_id, display_name, "2030-01-15T10:00:00"),
        )
        connection.execute(
            """INSERT INTO merchant_mappings(
            merchant_normalized,category,subcategory,updated_at
            ) VALUES(?,?,NULL,?)""",
            (merchant, category, "2030-01-15T10:00:00"),
        )
    connection.execute(
        """INSERT INTO recurring_profiles(
        canonical_group_id,display_name,verdict,recurring_type,cadence,
        cadence_months,lifecycle_status,updated_at
        ) VALUES(?,?,?,?,?,?,?,?)""",
        (
            "synthetic-gym", "Synthetic Gym", "recurring", "Fixed recurring",
            "Monthly", 1, "active", "2030-01-15T10:00:00",
        ),
    )
    connection.execute(
        """INSERT INTO recurring_profile_members(
        canonical_group_id,merchant_normalized,included,updated_at
        ) VALUES(?,?,?,?)""",
        ("synthetic-gym", "synthetic gym", 1, "2030-01-15T10:00:00"),
    )
    add_income(connection, month="2026-10", source_name="Synthetic salary", amount=8500)
    add_income(connection, month="2026-11", source_name="Synthetic salary", amount=8500)
    connection.execute(
        """INSERT INTO events(
        id,name,event_type,destination,start_date,end_date,status,budget,created_at,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (
            "synthetic-vienna-2026", "Synthetic Vienna 2026", "trip", "Vienna",
            "2026-10-01", "2026-11-30", "completed", "2500.00",
            "2030-01-15T10:00:00", "2030-01-15T10:00:00",
        ),
    )
    connection.commit()
    connection.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: browser_seed.py PATH")
    seed_database(Path(sys.argv[1]).resolve())
