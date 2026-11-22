"""Application workflows for event settings and transaction membership."""

from __future__ import annotations

import uuid
from datetime import datetime

from clearspend.database.connection import DatabaseTarget, database_transaction
from clearspend.events.rules import validate_event_settings


def save_transaction_event(
    database: DatabaseTarget, transaction_id: int, event_id: str,
) -> dict:
    if transaction_id <= 0:
        raise ValueError("A valid transaction is required")
    event_id = event_id.strip()
    with database_transaction(database) as connection:
        transaction = connection.execute(
            "SELECT id,merchant_raw FROM transactions WHERE id=?", (transaction_id,)
        ).fetchone()
        if not transaction:
            raise ValueError("Transaction not found")
        now = datetime.now().astimezone().isoformat()
        if not event_id:
            connection.execute(
                "DELETE FROM event_transactions WHERE transaction_id=?", (transaction_id,)
            )
            return {
                "status": "unassigned", "transaction_id": transaction_id,
                "merchant_raw": transaction["merchant_raw"], "event_id": None,
                "event_name": None, "event_type": None, "event_destination": None,
            }
        event = connection.execute(
            "SELECT id,name,event_type,destination FROM events WHERE id=? AND status!='cancelled'",
            (event_id,),
        ).fetchone()
        if not event:
            raise ValueError("Event not found")
        connection.execute(
            """INSERT INTO event_transactions(transaction_id,event_id,assigned_at)
            VALUES(?,?,?) ON CONFLICT(transaction_id) DO UPDATE SET
            event_id=excluded.event_id,assigned_at=excluded.assigned_at""",
            (transaction_id, event_id, now),
        )
        return {
            "status": "assigned", "transaction_id": transaction_id,
            "merchant_raw": transaction["merchant_raw"], "event_id": event["id"],
            "event_name": event["name"], "event_type": event["event_type"],
            "event_destination": event["destination"],
        }


def create_event(
    database: DatabaseTarget,
    name: str,
    event_type: str,
    start_date: str,
    end_date: str,
    budget: object,
    status: str,
    destination: str = "",
) -> dict:
    settings = validate_event_settings(
        name=name, event_type=event_type, destination=destination,
        start_date=start_date, end_date=end_date, budget=budget, status=status,
    )
    event_id = f"event-{uuid.uuid4().hex}"
    now = datetime.now().astimezone().isoformat()
    with database_transaction(database) as connection:
        connection.execute(
            """INSERT INTO events(
            id,name,event_type,destination,icon,start_date,end_date,status,budget,notes,created_at,updated_at
            ) VALUES(?,?,?,?,NULL,?,?,?,?,NULL,?,?)""",
            (event_id, settings.name, settings.event_type, settings.destination or None,
             settings.start.isoformat(), settings.end.isoformat(), settings.status,
             settings.budget, now, now),
        )
        row = connection.execute(
            """SELECT id,name,event_type,destination,icon,start_date,end_date,status,budget,notes
            FROM events WHERE id=?""", (event_id,),
        ).fetchone()
        return {"status": "created", "event": dict(row)}


def save_event_settings(
    database: DatabaseTarget,
    event_id: str,
    name: str,
    event_type: str,
    start_date: str,
    end_date: str,
    budget: object,
    status: str,
    destination: str = "",
) -> dict:
    event_id = event_id.strip()
    if not event_id or not name.strip():
        raise ValueError("Event and name are required")
    settings = validate_event_settings(
        name=name, event_type=event_type, destination=destination,
        start_date=start_date, end_date=end_date, budget=budget, status=status,
        allow_cancelled=True,
    )
    with database_transaction(database) as connection:
        if not connection.execute("SELECT 1 FROM events WHERE id=?", (event_id,)).fetchone():
            raise ValueError("Event not found")
        connection.execute(
            """UPDATE events SET name=?,event_type=?,destination=?,start_date=?,end_date=?,budget=?,status=?,updated_at=?
            WHERE id=?""",
            (settings.name, settings.event_type, settings.destination or None,
             settings.start.isoformat(), settings.end.isoformat(), settings.budget,
             settings.status, datetime.now().astimezone().isoformat(), event_id),
        )
        row = connection.execute(
            """SELECT id,name,event_type,destination,icon,start_date,end_date,status,budget,notes
            FROM events WHERE id=?""", (event_id,),
        ).fetchone()
        return {"status": "updated", "event": dict(row)}
