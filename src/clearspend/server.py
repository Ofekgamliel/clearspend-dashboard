from __future__ import annotations

import argparse
import cgi
import hashlib
import json
import math
import mimetypes
import re
import shutil
import sqlite3
import tempfile
import uuid
from collections import Counter
from datetime import date, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from clearspend.import_engine import (
    ImportDatabase,
    is_income_xlsx,
    parse_income_xlsx,
    parse_statement,
)
from tools.profile_samples import sha256_path


REPORTING_MONTH_SQL = "COALESCE(billing_month,substr(billing_date,1,7),substr(transaction_date,1,7))"
REPORTING_DATE_SQL = (
    "CASE WHEN billing_date IS NOT NULL THEN billing_date "
    "WHEN billing_month IS NOT NULL AND substr(transaction_date,1,7)=billing_month THEN transaction_date "
    "WHEN billing_month IS NOT NULL THEN billing_month||'-01' ELSE transaction_date END"
)


def personal_charge_sql(alias: str = "t") -> str:
    """Positive card charge after a reviewed reimbursement adjustment."""
    prefix = f"{alias}." if alias else ""
    return (
        f"CASE WHEN CAST({prefix}charged_amount AS REAL)>0 THEN "
        f"MAX(CAST({prefix}charged_amount AS REAL)-COALESCE((SELECT "
        "CAST(adjustment.reimbursed_amount AS REAL) FROM transaction_spending_adjustments adjustment "
        f"WHERE adjustment.transaction_id={prefix}id),0),0) ELSE 0 END"
    )


def staged_reference_data(connection: sqlite3.Connection) -> tuple[list[str], list[dict]]:
    categories = [row[0] for row in connection.execute(
        """SELECT DISTINCT category FROM (
        SELECT category FROM merchant_mappings
        UNION SELECT user_category category FROM transactions WHERE user_category IS NOT NULL
        UNION SELECT provider_category category FROM transactions WHERE provider_category IS NOT NULL
        ) WHERE category IS NOT NULL ORDER BY category"""
    )]
    identities = [dict(row) for row in connection.execute(
        """SELECT d.canonical_group_id,d.display_name,COUNT(DISTINCT d.merchant_normalized) aliases,
        COUNT(t.id) transactions,
        COALESCE((SELECT m.category FROM merchant_mappings m
          JOIN merchant_display_mappings dm ON dm.merchant_normalized=m.merchant_normalized
          WHERE dm.canonical_group_id=d.canonical_group_id GROUP BY m.category
          ORDER BY COUNT(*) DESC LIMIT 1),'Needs review') category
        FROM merchant_display_mappings d
        LEFT JOIN transactions t ON t.merchant_normalized=d.merchant_normalized
        GROUP BY d.canonical_group_id,d.display_name ORDER BY transactions DESC,d.display_name LIMIT 500"""
    )]
    return categories, identities


def analyze_staged_files(database: Path, uploads: list[tuple[str, Path]]) -> dict:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        categories, identities = staged_reference_data(connection)
        files: list[dict] = []
        merchant_groups: dict[str, dict] = {}
        for original_name, path in uploads:
            byte_hash = sha256_path(path)
            if path.suffix.lower() == ".xlsx" and is_income_xlsx(path):
                prior_file = connection.execute(
                    "SELECT id FROM income_imports WHERE byte_hash=? AND status IN ('imported','duplicate_file') ORDER BY id LIMIT 1",
                    (byte_hash,),
                ).fetchone()
                entries = parse_income_xlsx(path)
                existing = sum(bool(connection.execute(
                    "SELECT 1 FROM income_entries WHERE entry_key=?", (entry.entry_key,)
                ).fetchone()) for entry in entries)
                files.append({
                    "filename": original_name, "kind": "income", "format": "Income XLSX",
                    "provider": "income", "card_last4": None, "statement_range": None,
                    "parsed": len(entries), "duplicates": existing,
                    "new_rows": len(entries) - existing,
                    "status": "duplicate_file" if prior_file else "ready",
                    "reconciliation": {"official_total": None,
                        "parsed_total": round(sum(float(entry.amount) for entry in entries), 2),
                        "status": "not_applicable"},
                })
                continue
            prior_file = connection.execute(
                "SELECT id FROM imports WHERE byte_hash=? AND status IN ('imported','duplicate_file') ORDER BY id LIMIT 1",
                (byte_hash,),
            ).fetchone()
            statement = parse_statement(path)
            prior_semantic = connection.execute(
                "SELECT id FROM imports WHERE semantic_hash=? AND status IN ('imported','duplicate_content') ORDER BY id LIMIT 1",
                (statement.semantic_hash,),
            ).fetchone()
            duplicate_keys = {
                transaction.transaction_key for transaction in statement.transactions
                if connection.execute(
                    "SELECT 1 FROM transactions WHERE transaction_key=?", (transaction.transaction_key,)
                ).fetchone()
            }
            installment_plans = {
                (item.provider, item.card_last4, item.merchant_normalized, item.transaction_date,
                 item.original_amount, item.installment_total)
                for item in statement.transactions if item.installment_number is not None
            }
            parsed_total = round(sum(float(item.charged_amount or 0) for item in statement.transactions), 2)
            status = "duplicate_file" if prior_file else "duplicate_content" if prior_semantic else "ready"
            files.append({
                "filename": original_name, "kind": "statement", "format": path.suffix.upper().lstrip("."),
                "provider": statement.provider, "card_last4": statement.card_last4,
                "product_name": statement.product_name, "statement_range": statement.date_range,
                "parsed": len(statement.transactions), "duplicates": len(duplicate_keys),
                "new_rows": len(statement.transactions) - len(duplicate_keys), "status": status,
                "installment_plans": len(installment_plans),
                "reconciliation": {"official_total": None, "parsed_total": parsed_total,
                                   "status": "manual_required"},
            })
            if status in {"duplicate_file", "duplicate_content"}:
                continue
            for item in statement.transactions:
                if item.transaction_key in duplicate_keys:
                    continue
                group = merchant_groups.setdefault(item.merchant_normalized, {
                    "merchant_normalized": item.merchant_normalized,
                    "merchant_raw": item.merchant_raw, "transactions": 0, "amount": 0.0,
                    "providers": set(), "cards": set(), "first_date": item.transaction_date,
                    "last_date": item.transaction_date, "provider_categories": Counter(),
                })
                group["transactions"] += 1
                group["amount"] += abs(float(item.charged_amount or 0))
                group["providers"].add(item.provider)
                group["cards"].add(item.card_last4)
                if item.transaction_date and (not group["first_date"] or item.transaction_date < group["first_date"]):
                    group["first_date"] = item.transaction_date
                if item.transaction_date and (not group["last_date"] or item.transaction_date > group["last_date"]):
                    group["last_date"] = item.transaction_date
                if item.provider_category:
                    group["provider_categories"][item.provider_category] += 1
        merchants: list[dict] = []
        for normalized, group in merchant_groups.items():
            mapping = connection.execute(
                "SELECT category,subcategory FROM merchant_mappings WHERE merchant_normalized=?", (normalized,)
            ).fetchone()
            display = connection.execute(
                "SELECT canonical_group_id,display_name FROM merchant_display_mappings WHERE merchant_normalized=?",
                (normalized,),
            ).fetchone()
            provider_category = group["provider_categories"].most_common(1)[0][0] if group["provider_categories"] else None
            match_source = "exact_db" if mapping else "display_alias" if display else "provider" if provider_category else "unresolved"
            category = mapping["category"] if mapping else provider_category or "Needs review"
            merchants.append({
                "merchant_normalized": normalized, "merchant_raw": group["merchant_raw"],
                "transactions": group["transactions"], "amount": round(group["amount"], 2),
                "providers": sorted(group["providers"]), "cards": sorted(group["cards"]),
                "first_date": group["first_date"], "last_date": group["last_date"],
                "provider_category": provider_category, "match_source": match_source,
                "category": category, "subcategory": mapping["subcategory"] if mapping else None,
                "display_name": display["display_name"] if display else group["merchant_raw"],
                "canonical_group_id": display["canonical_group_id"] if display else None,
                "needs_review": not bool(mapping),
            })
        merchants.sort(key=lambda item: (not item["needs_review"], -item["transactions"], item["merchant_raw"]))
        return {"files": files, "merchants": merchants, "categories": categories,
                "display_identities": identities}
    finally:
        connection.close()


def commit_staged_batch(database: Path, batch: dict, decisions: list[dict]) -> dict:
    decision_map = {
        str(item.get("merchant_normalized", "")): item for item in decisions
        if str(item.get("merchant_normalized", ""))
    }
    backup_dir = database.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = backup_dir / f"clearspend-before-import-{stamp}.db"
    shutil.copy2(database, backup_path)
    db = ImportDatabase(database)
    results: list[dict] = []
    try:
        now = datetime.now().astimezone().isoformat()
        for normalized, decision in decision_map.items():
            resolution = str(decision.get("resolution", "needs_review"))
            scope = str(decision.get("scope", "exact"))
            category = str(decision.get("category", "")).strip()
            display_name = str(decision.get("display_name", "")).strip()
            if resolution not in {"needs_review", "exclude"} and category and scope == "exact":
                db.connection.execute(
                    """INSERT INTO merchant_mappings(merchant_normalized,category,subcategory,updated_at)
                    VALUES(?,?,NULL,?) ON CONFLICT(merchant_normalized) DO UPDATE SET
                    category=excluded.category,updated_at=excluded.updated_at""",
                    (normalized, category, now),
                )
            if resolution not in {"needs_review", "exclude"} and display_name and scope == "exact":
                group_id = str(decision.get("canonical_group_id", "")).strip()
                if not group_id:
                    display_key = re.sub(r"\s+", " ", display_name.casefold()).strip()
                    group_id = "custom:" + hashlib.sha256(display_key.encode("utf-8")).hexdigest()[:20]
                db.connection.execute(
                    """INSERT INTO merchant_display_mappings(
                    merchant_normalized,canonical_group_id,display_name,updated_at
                    ) VALUES(?,?,?,?) ON CONFLICT(merchant_normalized) DO UPDATE SET
                    canonical_group_id=excluded.canonical_group_id,
                    display_name=excluded.display_name,updated_at=excluded.updated_at""",
                    (normalized, group_id, display_name, now),
                )
        db.connection.commit()
        for staged_file in batch["uploads"]:
            result = db.import_file(staged_file["path"])
            if result.get("import_id"):
                table = "income_imports" if result.get("kind") == "income" else "imports"
                db.connection.execute(
                    f"UPDATE {table} SET original_name=? WHERE id=?",
                    (staged_file["filename"], result["import_id"]),
                )
            excluded = 0
            if result.get("import_id") and result.get("kind") != "income":
                new_rows = db.connection.execute(
                    """SELECT t.id,t.merchant_normalized FROM transactions t
                    JOIN import_transactions it ON it.transaction_id=t.id
                    WHERE it.import_id=? AND it.was_duplicate=0""", (result["import_id"],)
                ).fetchall()
                for row in new_rows:
                    decision = decision_map.get(row["merchant_normalized"], {})
                    resolution = str(decision.get("resolution", "needs_review"))
                    scope = str(decision.get("scope", "exact"))
                    category = str(decision.get("category", "")).strip()
                    if resolution == "exclude":
                        db.connection.execute(
                            "DELETE FROM import_transactions WHERE import_id=? AND transaction_id=?",
                            (result["import_id"], row["id"]),
                        )
                        db.connection.execute("DELETE FROM transactions WHERE id=?", (row["id"],))
                        excluded += 1
                    elif resolution == "needs_review" or (scope == "batch" and category):
                        override_category = "Needs review" if resolution == "needs_review" else category
                        db.connection.execute(
                            """INSERT INTO transaction_category_overrides(transaction_id,category,subcategory,updated_at)
                            VALUES(?,?,NULL,?) ON CONFLICT(transaction_id) DO UPDATE SET
                            category=excluded.category,updated_at=excluded.updated_at""",
                            (row["id"], override_category, now),
                        )
                if excluded:
                    db.connection.execute(
                        "UPDATE imports SET inserted_rows=MAX(inserted_rows-?,0) WHERE id=?",
                        (excluded, result["import_id"]),
                    )
                    result["inserted"] = max(int(result.get("inserted", 0)) - excluded, 0)
                    result["excluded"] = excluded
            db.connection.commit()
            result["filename"] = staged_file["filename"]
            results.append(result)
        return {"status": "committed", "backup": str(backup_path), "results": results}
    finally:
        db.close()


def add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    return date(year, month_zero + 1, 1)


def period_bounds(connection: sqlite3.Connection, period: str, month: str = "") -> tuple[str | None, str | None, str]:
    row = connection.execute(
        """SELECT MAX(value) FROM (
        SELECT COALESCE(billing_month,substr(billing_date,1,7),substr(transaction_date,1,7))||'-01' value
        FROM transactions WHERE transaction_date IS NOT NULL OR billing_month IS NOT NULL
        UNION ALL SELECT month||'-01' value FROM income_entries
        )"""
    ).fetchone()
    if not row or not row[0]:
        return None, None, "No transactions"
    latest = datetime.strptime(row[0], "%Y-%m-%d").date()
    if period == "month":
        latest_available = connection.execute(
            """SELECT MAX(value) FROM (
            SELECT COALESCE(billing_month,substr(billing_date,1,7),substr(transaction_date,1,7))||'-01' value
            FROM transactions WHERE transaction_date IS NOT NULL OR billing_month IS NOT NULL
            UNION ALL SELECT month||'-01' value FROM income_entries
            ) WHERE value<=?""",
            (date.today().isoformat(),),
        ).fetchone()[0]
        default_month = datetime.strptime(latest_available, "%Y-%m-%d").date() if latest_available else latest
        try:
            start = datetime.strptime(month, "%Y-%m").date() if month else default_month.replace(day=1)
        except ValueError:
            start = default_month.replace(day=1)
        end = add_months(start, 1) - timedelta(days=1)
        label = start.strftime("%B %Y")
    elif period == "year":
        start = date(latest.year, 1, 1)
        end = date(latest.year, 12, 31)
        label = str(latest.year)
    else:
        first = connection.execute(
            """SELECT MIN(value) FROM (
            SELECT COALESCE(billing_month,substr(billing_date,1,7),substr(transaction_date,1,7))||'-01' value
            FROM transactions WHERE transaction_date IS NOT NULL OR billing_month IS NOT NULL
            UNION ALL SELECT month||'-01' value FROM income_entries
            )"""
        ).fetchone()[0]
        start = datetime.strptime(first, "%Y-%m-%d").date()
        end = latest
        label = f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}"
    return start.isoformat(), end.isoformat(), label


def dashboard_payload(database: Path, period: str, card: str, month: str = "") -> dict:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        start, end, label = period_bounds(connection, period, month)
        period_parameters: list[object] = [(start or "0000-00")[:7], (end or "9999-99")[:7]]
        conditions = [f"{REPORTING_MONTH_SQL} BETWEEN ? AND ?"]
        parameters = list(period_parameters)
        if card != "all" and ":" in card:
            provider, last4 = card.split(":", 1)
            conditions.extend(["provider = ?", "card_last4 = ?"])
            parameters.extend([provider, last4])
        where = " AND ".join(conditions)

        metrics = connection.execute(
            f"""SELECT
            COALESCE(SUM({personal_charge_sql()}),0) spent,
            COALESCE(ABS(SUM(CASE WHEN CAST(t.charged_amount AS REAL) < 0 THEN CAST(t.charged_amount AS REAL) ELSE 0 END)),0) refunds,
            COUNT(*) transactions,
            COUNT(DISTINCT {REPORTING_DATE_SQL}) active_days
            FROM transactions t WHERE {where}""",
            parameters,
        ).fetchone()
        spent = float(metrics["spent"])
        active_days = int(metrics["active_days"])

        income_row = connection.execute(
            """SELECT COALESCE(SUM(CAST(amount AS REAL)),0) total,COUNT(*) entries
            FROM income_entries WHERE month BETWEEN ? AND ?""",
            ((start or "0000-00-00")[:7], (end or "9999-99-99")[:7]),
        ).fetchone()
        all_card_spending = connection.execute(
            f"""SELECT
            COALESCE(SUM({personal_charge_sql()}),0) personal_spent,
            COALESCE(SUM(CASE WHEN CAST(t.charged_amount AS REAL)>0 THEN CAST(t.charged_amount AS REAL) ELSE 0 END),0) charges,
            COALESCE(ABS(SUM(CASE WHEN CAST(t.charged_amount AS REAL)<0 THEN CAST(t.charged_amount AS REAL) ELSE 0 END)),0) refunds
            FROM transactions t WHERE {REPORTING_MONTH_SQL} BETWEEN ? AND ?""",
            period_parameters,
        ).fetchone()
        income_total = float(income_row["total"])
        all_card_spent = float(all_card_spending["personal_spent"])
        all_card_charges = float(all_card_spending["charges"])
        all_card_refunds = float(all_card_spending["refunds"])
        net_spending = all_card_spent - all_card_refunds
        remaining = income_total - net_spending

        if period == "month":
            average_start = connection.execute(
                """SELECT MIN(value) FROM (
                SELECT COALESCE(billing_month,substr(billing_date,1,7),substr(transaction_date,1,7))||'-01' value
                FROM transactions WHERE transaction_date IS NOT NULL OR billing_month IS NOT NULL
                UNION ALL SELECT month||'-01' value FROM income_entries
                )"""
            ).fetchone()[0] or start
        else:
            average_start = start
        average_end = min(datetime.strptime(end, "%Y-%m-%d").date(), date.today()).isoformat() if end else date.today().isoformat()
        average_parameters = [(average_start or "0000-00")[:7], average_end[:7]]
        monthly_spending_rows = connection.execute(
            f"""SELECT {REPORTING_MONTH_SQL} month,
            SUM({personal_charge_sql()})
            - ABS(SUM(CASE WHEN CAST(t.charged_amount AS REAL)<0 THEN CAST(t.charged_amount AS REAL) ELSE 0 END)) net
            FROM transactions t WHERE {REPORTING_MONTH_SQL} BETWEEN ? AND ? GROUP BY {REPORTING_MONTH_SQL}""",
            average_parameters,
        ).fetchall()
        monthly_spending = {row["month"]: float(row["net"]) for row in monthly_spending_rows}
        monthly_income_rows = connection.execute(
            """SELECT month,SUM(CAST(amount AS REAL)) total FROM income_entries
            WHERE month BETWEEN ? AND ? GROUP BY month""",
            (average_parameters[0][:7], average_parameters[1][:7]),
        ).fetchall()
        monthly_income = {row["month"]: float(row["total"]) for row in monthly_income_rows}
        average_spending = (
            sum(monthly_spending.values()) / len(monthly_spending) if monthly_spending else 0
        )
        monthly_amounts_left = [
            total - monthly_spending.get(income_month, 0)
            for income_month, total in monthly_income.items()
        ]
        average_amount_left = (
            sum(monthly_amounts_left) / len(monthly_amounts_left) if monthly_amounts_left else None
        )
        current_month = date.today().strftime("%Y-%m")
        average_months = set(monthly_spending) | set(monthly_income)
        sorted_average_months = sorted(average_months)

        cards = [dict(row) for row in connection.execute(
            f"""SELECT t.provider,t.card_last4,
            COALESCE((SELECT i.product_name FROM imports i WHERE i.provider=t.provider AND i.card_last4=t.card_last4
                      AND i.product_name IS NOT NULL ORDER BY i.id LIMIT 1), UPPER(t.provider)) product_name,
            ROUND(SUM({personal_charge_sql()}),2) amount,
            COUNT(*) transactions
            FROM transactions t WHERE COALESCE(t.billing_month,substr(t.billing_date,1,7),substr(t.transaction_date,1,7)) BETWEEN ? AND ?
            GROUP BY t.provider,t.card_last4 ORDER BY amount DESC""",
            period_parameters,
        )]
        cards_total = sum(float(item["amount"]) for item in cards)
        for item in cards:
            item["key"] = f"{item['provider']}:{item['card_last4']}"
            item["share"] = round((item["amount"] / cards_total * 100), 1) if cards_total else 0

        categories = [dict(row) for row in connection.execute(
            f"""SELECT COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
            ROUND(SUM({personal_charge_sql()}),2) amount,
            COUNT(*) transactions FROM transactions t
            LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id WHERE {where}
            GROUP BY COALESCE(o.category,t.user_category,t.provider_category,'Needs review') HAVING amount > 0 ORDER BY amount DESC""",
            parameters,
        )]
        for item in categories:
            item["share"] = round((item["amount"] / spent * 100), 1) if spent else 0

        category_comparison = {"available": False, "previous_month": None}
        if period == "month":
            previous_month = add_months(datetime.strptime(start, "%Y-%m-%d").date(), -1).strftime("%Y-%m")
            previous_conditions = [f"{REPORTING_MONTH_SQL} = ?"]
            previous_parameters: list[object] = [previous_month]
            if card != "all" and ":" in card:
                provider, last4 = card.split(":", 1)
                previous_conditions.extend(["t.provider = ?", "t.card_last4 = ?"])
                previous_parameters.extend([provider, last4])
            previous_where = " AND ".join(previous_conditions)
            previous_count = int(connection.execute(
                f"SELECT COUNT(*) FROM transactions t WHERE {previous_where}",
                previous_parameters,
            ).fetchone()[0])
            previous_rows = connection.execute(
                f"""SELECT COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
                ROUND(SUM({personal_charge_sql()}),2) amount
                FROM transactions t
                LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
                WHERE {previous_where}
                GROUP BY COALESCE(o.category,t.user_category,t.provider_category,'Needs review')""",
                previous_parameters,
            ).fetchall()
            previous_amounts = {row["category"]: float(row["amount"]) for row in previous_rows}
            category_comparison = {"available": previous_count > 0, "previous_month": previous_month}
            for item in categories:
                item["previous_amount"] = round(previous_amounts.get(item["category"], 0), 2)
                if not previous_count:
                    item["comparison"] = "unavailable"
                    item["change_percent"] = None
                    continue
                previous_amount = item["previous_amount"]
                if previous_amount <= 0:
                    item["comparison"] = "new"
                    item["change_percent"] = None
                    continue
                change_percent = round((float(item["amount"]) - previous_amount) / previous_amount * 100)
                item["change_percent"] = change_percent
                item["comparison"] = "up" if change_percent > 0 else "down" if change_percent < 0 else "same"

        recent = [dict(row) for row in connection.execute(
            f"""SELECT t.merchant_raw,COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
            COALESCE(o.subcategory,t.user_subcategory) subcategory,t.provider,t.card_last4,
            t.transaction_date,t.billing_date,t.billing_month,t.billing_month_source,
            CAST(t.charged_amount AS REAL) amount,{personal_charge_sql()} personal_amount,t.charged_currency,
            a.adjustment_type,a.reimbursed_amount,a.reimbursement_date
            FROM transactions t LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
            LEFT JOIN transaction_spending_adjustments a ON a.transaction_id=t.id
            WHERE {where} ORDER BY COALESCE(t.billing_date,t.billing_month||'-01',t.transaction_date) DESC,t.id DESC LIMIT 6""",
            parameters,
        )]

        purchase_activity_summary = None
        if period == "month":
            purchase_conditions = ["t.transaction_date BETWEEN ? AND ?"]
            purchase_parameters: list[object] = [start or "0000-00-00", end or "9999-99-99"]
            if card != "all" and ":" in card:
                provider, last4 = card.split(":", 1)
                purchase_conditions.extend(["t.provider = ?", "t.card_last4 = ?"])
                purchase_parameters.extend([provider, last4])
            purchase_where = " AND ".join(purchase_conditions)
            purchase_rows = [dict(row) for row in connection.execute(
                f"""WITH purchase_rows AS (
                SELECT t.transaction_date bucket,
                       COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
                       {personal_charge_sql()} amount,1 purchases,0 installment_plans
                FROM transactions t LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
                WHERE {purchase_where} AND t.installment_number IS NULL
                UNION ALL
                SELECT t.transaction_date bucket,
                COALESCE(
                  MAX(CASE WHEN t.installment_number=1
                      THEN COALESCE(o.category,t.user_category,t.provider_category,'Needs review') END),
                  MAX(COALESCE(o.category,t.user_category,t.provider_category,'Needs review'))
                ) category,
                CASE
                  WHEN MAX(t.original_amount) IS NOT NULL
                   AND COALESCE(MAX(t.original_currency),'')=COALESCE(MAX(t.charged_currency),'')
                    THEN CAST(MAX(t.original_amount) AS REAL)
                  ELSE ROUND(AVG(CAST(t.charged_amount AS REAL))*MAX(t.installment_total),2)
                END amount,1 purchases,1 installment_plans
                FROM transactions t LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
                WHERE {purchase_where} AND t.installment_number IS NOT NULL
                GROUP BY t.provider,t.card_last4,t.merchant_normalized,t.transaction_date,
                         t.original_amount,t.original_currency,t.charged_currency,t.installment_total
                )
                SELECT bucket,category,ROUND(SUM(amount),2) amount,SUM(purchases) purchases,
                       SUM(installment_plans) installment_plans
                FROM purchase_rows GROUP BY bucket,category ORDER BY bucket,amount DESC""",
                purchase_parameters + purchase_parameters,
            )]
            activity_by_day: dict[str, dict] = {}
            for row in purchase_rows:
                day = activity_by_day.setdefault(row["bucket"], {
                    "bucket": row["bucket"], "amount": 0.0, "categories": []
                })
                amount = float(row["amount"])
                day["amount"] += amount
                day["categories"].append({"category": row["category"], "amount": round(amount, 2)})
            trend = []
            for day in activity_by_day.values():
                day["amount"] = round(day["amount"], 2)
                trend.append(day)
            purchase_activity_summary = {
                "total": round(sum(float(row["amount"]) for row in purchase_rows), 2),
                "purchases": int(sum(int(row["purchases"]) for row in purchase_rows)),
                "active_days": len(activity_by_day),
                "installment_plans": int(sum(int(row["installment_plans"]) for row in purchase_rows)),
                "billed_charges": round(spent, 2),
                "billed_refunds": round(float(metrics["refunds"]), 2),
            }
        else:
            trend_spending = [dict(row) for row in connection.execute(
                f"""SELECT {REPORTING_MONTH_SQL} bucket,
                ROUND(SUM({personal_charge_sql()})+
                  SUM(CASE WHEN CAST(t.charged_amount AS REAL)<0 THEN CAST(t.charged_amount AS REAL) ELSE 0 END),2) amount
                FROM transactions t WHERE {where} GROUP BY {REPORTING_MONTH_SQL} ORDER BY bucket""",
                parameters,
            )]
            trend_income = {
                row["month"]: float(row["total"])
                for row in connection.execute(
                    """SELECT month,SUM(CAST(amount AS REAL)) total FROM income_entries
                    WHERE month BETWEEN ? AND ? GROUP BY month""",
                    ((start or "0000-00-00")[:7], (end or "9999-99-99")[:7]),
                )
            }
            spending_by_month = {row["bucket"]: float(row["amount"]) for row in trend_spending}
            trend = [
                {
                    "bucket": bucket,
                    "amount": round(spending_by_month.get(bucket, 0), 2),
                    "income": round(trend_income.get(bucket, 0), 2),
                }
                for bucket in sorted(set(spending_by_month) | set(trend_income))
            ]

        uncategorized = connection.execute(
            f"SELECT COUNT(DISTINCT merchant_normalized) FROM transactions WHERE {where} AND user_category IS NULL AND provider_category IS NULL",
            parameters,
        ).fetchone()[0]
        duplicate_rows = connection.execute("SELECT COALESCE(SUM(duplicate_rows),0) FROM imports").fetchone()[0]
        latest_import = connection.execute(
            "SELECT original_name,imported_at,status FROM imports ORDER BY id DESC LIMIT 1"
        ).fetchone()
        largest = connection.execute(
            f"""SELECT merchant_raw,{personal_charge_sql()} amount FROM transactions t
            WHERE {where} AND {personal_charge_sql()}>0 ORDER BY amount DESC LIMIT 1""",
            parameters,
        ).fetchone()
        return {
            "period": {"key": period, "start": start, "end": end, "label": label},
            "selected_card": card,
            "metrics": {
                "spent": round(spent, 2),
                "refunds": round(float(metrics["refunds"]), 2),
                "transactions": int(metrics["transactions"]),
                "daily_average": round(spent / active_days, 2) if active_days else 0,
                "active_days": active_days,
            },
            "income_summary": {
                "has_income": bool(income_row["entries"]),
                "income": round(income_total, 2),
                "spending": round(net_spending, 2),
                "charges": round(all_card_charges, 2),
                "refunds": round(all_card_refunds, 2),
                "remaining": round(remaining, 2),
                "remaining_percentage": round(remaining / income_total * 100, 1) if income_total else None,
                "spent_percentage": round(net_spending / income_total * 100, 1) if income_total else None,
                "scope": "all_cards",
                "averages": {
                    "spending": round(average_spending, 2),
                    "amount_left": round(average_amount_left, 2) if average_amount_left is not None else None,
                    "spending_months": len(monthly_spending),
                    "amount_left_months": len(monthly_amounts_left),
                    "start_month": sorted_average_months[0] if sorted_average_months else None,
                    "end_month": sorted_average_months[-1] if sorted_average_months else None,
                    "current_month_partial": current_month in average_months,
                },
            },
            "cards": cards,
            "categories": categories,
            "category_comparison": category_comparison,
            "recent_transactions": recent,
            "trend": trend,
            "trend_mode": "purchase_activity" if period == "month" else "billing_summary",
            "purchase_activity_summary": purchase_activity_summary,
            "insights": {
                "merchants_needing_review": int(uncategorized),
                "duplicate_rows_prevented": int(duplicate_rows),
                "largest_transaction": dict(largest) if largest else None,
            },
            "latest_import": dict(latest_import) if latest_import else None,
            "available_months": [row[0] for row in connection.execute(
                """SELECT month FROM (
                SELECT DISTINCT COALESCE(billing_month,substr(billing_date,1,7),substr(transaction_date,1,7)) month
                FROM transactions WHERE transaction_date IS NOT NULL OR billing_month IS NOT NULL
                UNION SELECT DISTINCT month FROM income_entries
                ) ORDER BY month DESC"""
            )],
        }
    finally:
        connection.close()


def filtered_where(connection: sqlite3.Connection, period: str, card: str, month: str = "") -> tuple[str, list[object], dict]:
    start, end, label = period_bounds(connection, period, month)
    conditions = [f"{REPORTING_MONTH_SQL} BETWEEN ? AND ?"]
    parameters: list[object] = [(start or "0000-00")[:7], (end or "9999-99")[:7]]
    if card != "all" and ":" in card:
        provider, last4 = card.split(":", 1)
        conditions.extend(["provider = ?", "card_last4 = ?"])
        parameters.extend([provider, last4])
    return " AND ".join(conditions), parameters, {"key": period, "start": start, "end": end, "label": label}


def transactions_payload(
    database: Path,
    period: str,
    card: str,
    search: str = "",
    month: str = "",
    category: str = "",
) -> dict:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        where, parameters, period_data = filtered_where(connection, period, card, month)
        if search.strip():
            where += " AND (t.merchant_raw LIKE ? OR COALESCE(o.category,t.user_category,t.provider_category,'Needs review') LIKE ?)"
            term = f"%{search.strip()}%"
            parameters.extend([term, term])
        if category.strip():
            where += " AND COALESCE(o.category,t.user_category,t.provider_category,'Needs review') = ?"
            parameters.append(category.strip())
        total = connection.execute(
            f"""SELECT COUNT(*) FROM transactions t
            LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id WHERE {where}""",
            parameters,
        ).fetchone()[0]
        rows = [dict(row) for row in connection.execute(
            f"""SELECT t.id,t.merchant_raw,t.merchant_normalized,
            COALESCE(d.canonical_group_id,t.merchant_normalized) canonical_merchant_id,
            COALESCE(d.display_name,t.merchant_raw) merchant_display_name,
            COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
            COALESCE(o.subcategory,t.user_subcategory) subcategory,
            COALESCE(t.user_category,t.provider_category,'Needs review') merchant_category,
            CASE WHEN o.transaction_id IS NOT NULL THEN 'transaction_override'
                 WHEN t.user_category IS NOT NULL THEN 'merchant_rule'
                 WHEN t.provider_category IS NOT NULL THEN 'provider' ELSE 'unmapped' END category_source,
            provider,card_last4,source_sheet,transaction_date,billing_date,
            billing_month,billing_month_source,installment_number,installment_total,
            CAST(charged_amount AS REAL) amount,charged_currency,
            {personal_charge_sql()} personal_amount,a.adjustment_type,
            CAST(a.reimbursed_amount AS REAL) reimbursed_amount,
            a.reimbursement_date,a.note reimbursement_note,
            CAST(original_amount AS REAL) original_amount,original_currency,
            transaction_type,voucher_number,notes,execution_method,exchange_rate
            FROM transactions t LEFT JOIN merchant_display_mappings d
              ON d.merchant_normalized=t.merchant_normalized
            LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
            LEFT JOIN transaction_spending_adjustments a ON a.transaction_id=t.id
            WHERE {where} ORDER BY COALESCE(billing_date,billing_month||'-01',transaction_date) DESC,t.id DESC LIMIT 1000""",
            parameters,
        )]
        return {"period": period_data, "selected_card": card, "total": int(total), "transactions": rows}
    finally:
        connection.close()


def categories_payload(database: Path, period: str, card: str, month: str = "") -> dict:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        where, parameters, period_data = filtered_where(connection, period, card, month)
        total = float(connection.execute(
            f"SELECT COALESCE(SUM({personal_charge_sql()}),0) FROM transactions t WHERE {where}",
            parameters,
        ).fetchone()[0])
        rows = [dict(row) for row in connection.execute(
            f"""SELECT COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
            ROUND(SUM({personal_charge_sql()}),2) amount,
            COUNT(*) transactions,COUNT(DISTINCT COALESCE(d.canonical_group_id,t.merchant_normalized)) merchants
            FROM transactions t LEFT JOIN merchant_display_mappings d
              ON d.merchant_normalized=t.merchant_normalized
            LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
            WHERE {where} GROUP BY COALESCE(o.category,t.user_category,t.provider_category,'Needs review')
            ORDER BY amount DESC""",
            parameters,
        )]
        for row in rows:
            row["share"] = round(float(row["amount"]) / total * 100, 1) if total else 0
        return {"period": period_data, "selected_card": card, "total": round(total, 2), "categories": rows}
    finally:
        connection.close()


def _month_number(value: str) -> int:
    year, month = (int(part) for part in value.split("-", 1))
    return year * 12 + month - 1


def _add_months(value: str, count: int) -> str:
    number = _month_number(value) + count
    return f"{number // 12:04d}-{number % 12 + 1:02d}"


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _month_history(
    amounts: dict[str, float], end_month: str, cadence_months: int,
    lifecycle_status: str = "active", end_profile_month: str | None = None,
) -> list[dict]:
    if not amounts:
        return []
    first_month = min(amounts)
    start_month = max(_month_number(first_month), _month_number(end_month) - 11)
    history: list[dict] = []
    for number in range(start_month, _month_number(end_month) + 1):
        current = f"{number // 12:04d}-{number % 12 + 1:02d}"
        amount = round(amounts.get(current, 0.0), 2)
        after_end = lifecycle_status == "ended" and bool(end_profile_month) and current > end_profile_month
        expected = (
            cadence_months > 0 and not after_end and lifecycle_status == "active"
            and (number - _month_number(first_month)) % cadence_months == 0
        )
        if expected and cadence_months >= 6:
            expected = not any(amounts.get(_add_months(current, offset), 0) for offset in (-1, 1))
        history.append({
            "month": current,
            "amount": amount if amount else None,
            "state": "charged" if amount else "missing" if expected else "not_expected",
        })
    return history


def recurring_payload(
    database: Path, period: str, card: str, month: str = "",
) -> dict:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        start, end, label = period_bounds(connection, period, month)
        start_month = (start or "0000-00")[:7]
        end_month = (end or date.today().isoformat())[:7]
        card_sql = ""
        card_parameters: list[object] = []
        if card != "all" and ":" in card:
            provider, last4 = card.split(":", 1)
            card_sql = " AND t.provider=? AND t.card_last4=?"
            card_parameters = [provider, last4]

        transaction_rows = connection.execute(
            f"""SELECT COALESCE(d.canonical_group_id,t.merchant_normalized) canonical_group_id,
            COALESCE(d.display_name,p.display_name,t.merchant_raw) display_name,
            t.merchant_raw source_alias,
            COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
            {REPORTING_MONTH_SQL} report_month,CAST(t.charged_amount AS REAL) amount,
            p.recurring_type,p.cadence,p.cadence_months,p.lifecycle_status,p.end_month
            FROM transactions t
            LEFT JOIN merchant_display_mappings d ON d.merchant_normalized=t.merchant_normalized
            JOIN recurring_profile_members rpm
              ON rpm.canonical_group_id=COALESCE(d.canonical_group_id,t.merchant_normalized)
             AND rpm.merchant_normalized=t.merchant_normalized AND rpm.included=1
            JOIN recurring_profiles p ON p.canonical_group_id=rpm.canonical_group_id
             AND p.verdict='recurring'
            LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
            WHERE CAST(t.charged_amount AS REAL)>0 AND t.installment_number IS NULL
              AND {REPORTING_MONTH_SQL}<=?{card_sql}
            ORDER BY report_month,t.id""",
            [end_month, *card_parameters],
        ).fetchall()
        grouped: dict[tuple[str, str], dict] = {}
        for row in transaction_rows:
            key = (row["canonical_group_id"], row["category"])
            item = grouped.setdefault(key, {
                "canonical_group_id": row["canonical_group_id"],
                "display_name": row["display_name"], "category": row["category"],
                "recurring_type": row["recurring_type"] or "Other recurring",
                "cadence": row["cadence"] or "Unknown",
                "cadence_months": int(row["cadence_months"] or 0),
                "lifecycle_status": row["lifecycle_status"] or "active",
                "end_month": row["end_month"], "months": {}, "source_aliases": set(),
            })
            item["source_aliases"].add(row["source_alias"])
            report_month = row["report_month"]
            if report_month:
                item["months"][report_month] = item["months"].get(report_month, 0.0) + float(row["amount"])

        series: list[dict] = []
        trend_totals: dict[str, float] = {}
        for item in grouped.values():
            months = item["months"]
            if not months:
                continue
            recorded_months = sorted(months)
            last_month = recorded_months[-1]
            cadence_months = item["cadence_months"]
            lifecycle = item["lifecycle_status"]
            profile_end = item["end_month"]
            actual = months.get(start_month) if period == "month" else None
            annual_state = None
            due_month = None
            if period == "month" and cadence_months == 12:
                if actual is not None:
                    annual_state = "paid"
                    due_month = start_month
                else:
                    due_month = _add_months(last_month, 12)
                    distance = _month_number(start_month) - _month_number(due_month)
                    annual_state = "upcoming" if distance == -1 else "due" if distance == 0 else "overdue" if distance > 0 else None
                    if annual_state is None:
                        continue
            if period == "month":
                if last_month > end_month or (lifecycle == "ended" and profile_end and start_month > profile_end):
                    continue
            elif not any(start_month <= current <= end_month for current in recorded_months):
                continue

            scoped_amount = round(sum(value for current, value in months.items() if start_month <= current <= end_month), 2)
            scoped_months = [current for current in recorded_months if start_month <= current <= end_month]
            previous_amounts = [months[current] for current in recorded_months[:-1]]
            typical = _median(list(months.values()))
            increased = bool(previous_amounts and months[last_month] > previous_amounts[-1] * 1.15)
            overdue = cadence_months > 0 and _month_number(end_month) - _month_number(last_month) > max(cadence_months + 1, 2)
            if lifecycle != "active":
                status = lifecycle
            elif annual_state:
                status = annual_state
            elif actual is None and period == "month":
                status = "missing" if overdue else "expected"
            elif increased:
                status = "increased"
            elif item["recurring_type"] == "Usage-based recurring":
                status = "variable"
            else:
                status = "confirmed"
            if annual_state == "paid":
                coverage = f"Paid {start_month}; next {_add_months(start_month, 12)}"
            elif annual_state:
                coverage = f"{annual_state.title()} {due_month}"
            elif item["recurring_type"] == "Usage-based recurring":
                recent = list(months.values())[-6:]
                coverage = f"Recent range {min(recent):.2f}–{max(recent):.2f}"
            else:
                coverage = f"Expected {_add_months(last_month, cadence_months)}" if cadence_months else "No reliable schedule"
            amount = actual if period == "month" else scoped_amount / max(len({current for current in recorded_months if start_month <= current <= end_month}), 1) if period == "year" else scoped_amount
            row = {
                **{key: item[key] for key in (
                    "canonical_group_id", "display_name", "category", "recurring_type",
                    "cadence", "cadence_months", "lifecycle_status", "end_month",
                )},
                "source_aliases": sorted(item["source_aliases"]),
                "series_id": f"{item['canonical_group_id']}\u0000{item['category']}",
                "amount": round(amount, 2) if amount is not None else None,
                "amount_kind": "billed" if period == "month" else "monthly_average" if period == "year" else "period_total",
                "coverage": coverage, "status": status, "last_billed_month": last_month,
                "billed_months": len(scoped_months), "typical_amount": round(typical, 2),
                "history": _month_history(months, end_month, cadence_months, lifecycle, profile_end),
            }
            series.append(row)
            for current, value in months.items():
                if start_month <= current <= end_month:
                    trend_totals[current] = trend_totals.get(current, 0.0) + value

        series.sort(key=lambda item: (-(item["amount"] or 0), item["display_name"]))

        installment_rows = connection.execute(
            f"""SELECT t.provider,t.card_last4,COALESCE(d.canonical_group_id,t.merchant_normalized) canonical_group_id,
            COALESCE(d.display_name,t.merchant_raw) display_name,t.merchant_raw source_alias,
            COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
            t.transaction_date,t.original_amount,t.installment_number,t.installment_total,
            {REPORTING_MONTH_SQL} report_month,CAST(t.charged_amount AS REAL) amount
            FROM transactions t LEFT JOIN merchant_display_mappings d ON d.merchant_normalized=t.merchant_normalized
            LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
            WHERE CAST(t.charged_amount AS REAL)>0 AND t.installment_number IS NOT NULL
              AND {REPORTING_MONTH_SQL}<=?{card_sql} ORDER BY report_month,t.id""",
            [end_month, *card_parameters],
        ).fetchall()
        plans: dict[tuple, dict] = {}
        for row in installment_rows:
            key = (row["provider"], row["card_last4"], row["canonical_group_id"], row["transaction_date"], row["original_amount"], row["installment_total"])
            plan = plans.setdefault(key, {"display_name": row["display_name"], "source_alias": row["source_alias"], "category": row["category"], "total": int(row["installment_total"] or 0), "rows": []})
            plan["rows"].append(dict(row))
        commitments: list[dict] = []
        for plan in plans.values():
            scoped = [row for row in plan["rows"] if start_month <= row["report_month"] <= end_month]
            if not scoped:
                continue
            current = max(int(row["installment_number"] or 0) for row in plan["rows"])
            paid = sum(float(row["amount"]) for row in plan["rows"])
            charge = _median([float(row["amount"]) for row in plan["rows"]])
            remaining_count = max(plan["total"] - current, 0)
            history_amounts: dict[str, float] = {}
            for row in plan["rows"]:
                history_amounts[row["report_month"]] = history_amounts.get(row["report_month"], 0.0) + float(row["amount"])
            commitments.append({
                "display_name": plan["display_name"], "source_alias": plan["source_alias"], "category": plan["category"],
                "progress": f"{current} / {plan['total']}", "current_installment": current,
                "total_installments": plan["total"], "charge": round(charge, 2),
                "paid": round(paid, 2), "remaining": round(remaining_count * charge, 2),
                "remaining_count": remaining_count, "status": "active" if remaining_count else "completed",
                "history": _month_history(history_amounts, end_month, 0),
            })
        commitments.sort(key=lambda item: (-item["remaining"], item["display_name"]))

        recurring_billed = round(sum(
            sum(float(row["amount"]) for row in transaction_rows if row["canonical_group_id"] == item["canonical_group_id"] and row["category"] == item["category"] and start_month <= row["report_month"] <= end_month)
            for item in series
        ), 2)
        installment_billed = round(sum(float(row["amount"]) for row in installment_rows if start_month <= row["report_month"] <= end_month), 2)
        month_count = max(len({
            row["report_month"] for row in connection.execute(
                f"SELECT {REPORTING_MONTH_SQL} report_month FROM transactions t WHERE {REPORTING_MONTH_SQL} BETWEEN ? AND ?{card_sql}",
                [start_month, end_month, *card_parameters],
            ) if row["report_month"]
        }), 1)
        spending = float(connection.execute(
            f"SELECT COALESCE(SUM(CASE WHEN CAST(t.charged_amount AS REAL)>0 THEN CAST(t.charged_amount AS REAL) ELSE 0 END),0) FROM transactions t WHERE {REPORTING_MONTH_SQL} BETWEEN ? AND ?{card_sql}",
            [start_month, end_month, *card_parameters],
        ).fetchone()[0])
        verdicts = connection.execute(
            """SELECT SUM(review_count) reviewed,
            SUM(CASE WHEN verdict='recurring' THEN review_count ELSE 0 END) recurring,
            SUM(CASE WHEN verdict='not_recurring' THEN review_count ELSE 0 END) not_recurring
            FROM recurring_profiles"""
        ).fetchone()
        attention = sum(item["status"] in {"missing", "increased", "due", "overdue", "unknown"} for item in series)
        recurring_average = recurring_billed if period == "month" else recurring_billed / month_count
        installment_average = installment_billed if period == "month" else installment_billed / month_count
        return {
            "period": {"key": period, "start": start, "end": end, "label": label},
            "selected_card": card,
            "metrics": {
                "recurring_billed": recurring_billed, "recurring_average": round(recurring_average, 2),
                "active_series": len(series), "needs_attention": attention,
                "installment_billed": installment_billed, "installment_average": round(installment_average, 2),
                "installment_plans": len(commitments),
                "recurring_share": round(recurring_billed / spending * 100, 1) if spending else 0,
                "installment_share": round(installment_billed / spending * 100, 1) if spending else 0,
            },
            "series": series, "commitments": commitments,
            "trend": [{"month": current, "amount": round(value, 2)} for current, value in sorted(trend_totals.items())],
            "verdict_summary": {
                "reviewed": int(verdicts["reviewed"] or 0),
                "recurring": int(verdicts["recurring"] or 0),
                "not_recurring": int(verdicts["not_recurring"] or 0),
                "unresolved": 0,
            },
        }
    finally:
        connection.close()


def save_recurring_profile(
    database: Path, canonical_group_id: str, recurring_type: str,
    cadence: str, lifecycle_status: str, end_month: str,
) -> dict:
    canonical_group_id = canonical_group_id.strip()
    allowed_types = {"Fixed recurring", "Usage-based recurring", "Scheduled obligation", "Other recurring"}
    cadence_months = {"Weekly": 0, "Monthly": 1, "Every 2 months": 2, "Quarterly": 3, "Every 6 months": 6, "Yearly": 12, "Custom": 0, "Irregular": 0, "Unknown": 0}
    lifecycle_status = lifecycle_status.strip().lower()
    if not canonical_group_id:
        raise ValueError("A recurring profile is required")
    if recurring_type not in allowed_types:
        raise ValueError("Invalid recurring type")
    if cadence not in cadence_months:
        raise ValueError("Invalid cadence")
    if lifecycle_status not in {"active", "ended", "paused", "unknown"}:
        raise ValueError("Invalid lifecycle status")
    end_month = end_month.strip()
    if lifecycle_status == "ended" and end_month and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", end_month):
        raise ValueError("End month must use YYYY-MM")
    if lifecycle_status != "ended":
        end_month = ""
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        existing = connection.execute(
            "SELECT * FROM recurring_profiles WHERE canonical_group_id=? AND verdict='recurring'",
            (canonical_group_id,),
        ).fetchone()
        if not existing:
            raise ValueError("Recurring profile was not found")
        connection.execute(
            """UPDATE recurring_profiles SET recurring_type=?,cadence=?,cadence_months=?,
            lifecycle_status=?,end_month=?,updated_at=? WHERE canonical_group_id=?""",
            (recurring_type, cadence, cadence_months[cadence], lifecycle_status,
             end_month or None, datetime.now().isoformat(timespec="seconds"), canonical_group_id),
        )
        connection.commit()
        return dict(connection.execute(
            "SELECT * FROM recurring_profiles WHERE canonical_group_id=?", (canonical_group_id,)
        ).fetchone())
    finally:
        connection.close()


def manage_recurring_profile(
    database: Path, canonical_group_id: str, verdict: str,
    recurring_type: str = "", cadence: str = "",
    lifecycle_status: str = "active", end_month: str = "",
    included_aliases: list[str] | None = None,
) -> dict:
    canonical_group_id = canonical_group_id.strip()
    verdict = verdict.strip()
    recurring_type = recurring_type.strip()
    cadence = cadence.strip()
    lifecycle_status = lifecycle_status.strip().lower()
    end_month = end_month.strip()
    allowed_types = {"Fixed recurring", "Usage-based recurring", "Scheduled obligation", "Other recurring"}
    cadence_months = {"Weekly": 0, "Monthly": 1, "Every 2 months": 2, "Quarterly": 3, "Every 6 months": 6, "Yearly": 12, "Custom": 0, "Irregular": 0, "Unknown": 0}
    if not canonical_group_id:
        raise ValueError("A merchant group is required")
    if verdict not in {"recurring", "not_recurring"}:
        raise ValueError("Invalid recurring verdict")
    if verdict == "recurring":
        if recurring_type not in allowed_types:
            raise ValueError("Invalid recurring type")
        if cadence not in cadence_months:
            raise ValueError("Invalid cadence")
        if lifecycle_status not in {"active", "ended", "paused", "unknown"}:
            raise ValueError("Invalid lifecycle status")
        if lifecycle_status == "ended" and not end_month:
            raise ValueError("An end month is required for an ended profile")
        if end_month and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", end_month):
            raise ValueError("End month must use YYYY-MM")
        if lifecycle_status != "ended":
            end_month = ""
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        merchant_rows = connection.execute(
            """SELECT DISTINCT t.merchant_normalized,
            COALESCE(d.display_name,t.merchant_raw) display_name
            FROM transactions t
            LEFT JOIN merchant_display_mappings d ON d.merchant_normalized=t.merchant_normalized
            WHERE COALESCE(d.canonical_group_id,t.merchant_normalized)=?
            ORDER BY t.merchant_normalized""",
            (canonical_group_id,),
        ).fetchall()
        if not merchant_rows:
            raise ValueError("Merchant group was not found")
        merchant = merchant_rows[0]
        available_aliases = {row["merchant_normalized"] for row in merchant_rows}
        if included_aliases is None:
            selected_aliases = set(available_aliases)
        else:
            selected_aliases = {str(alias).strip() for alias in included_aliases if str(alias).strip()}
            if not selected_aliases.issubset(available_aliases):
                raise ValueError("A recurring alias does not belong to this merchant group")
        if verdict == "recurring" and not selected_aliases:
            raise ValueError("Select at least one original merchant name for recurring tracking")
        existing = connection.execute(
            "SELECT * FROM recurring_profiles WHERE canonical_group_id=?",
            (canonical_group_id,),
        ).fetchone()
        now = datetime.now().astimezone().isoformat()
        if verdict == "not_recurring":
            if existing:
                connection.execute(
                    """UPDATE recurring_profiles SET verdict='not_recurring',display_name=?,updated_at=?
                    WHERE canonical_group_id=?""",
                    (merchant["display_name"], now, canonical_group_id),
                )
            else:
                connection.execute(
                    """INSERT INTO recurring_profiles(
                    canonical_group_id,display_name,verdict,lifecycle_status,updated_at
                    ) VALUES(?,?,'not_recurring','active',?)""",
                    (canonical_group_id, merchant["display_name"], now),
                )
            selected_aliases = set()
        else:
            connection.execute(
                """INSERT INTO recurring_profiles(
                canonical_group_id,display_name,verdict,recurring_type,cadence,cadence_months,
                lifecycle_status,end_month,updated_at
                ) VALUES(?,?,'recurring',?,?,?,?,?,?)
                ON CONFLICT(canonical_group_id) DO UPDATE SET
                display_name=excluded.display_name,verdict='recurring',
                recurring_type=excluded.recurring_type,cadence=excluded.cadence,
                cadence_months=excluded.cadence_months,
                lifecycle_status=excluded.lifecycle_status,end_month=excluded.end_month,
                updated_at=excluded.updated_at""",
                (canonical_group_id, merchant["display_name"], recurring_type, cadence,
                 cadence_months[cadence], lifecycle_status, end_month or None, now),
            )
        for alias in available_aliases:
            connection.execute(
                """INSERT INTO recurring_profile_members(
                canonical_group_id,merchant_normalized,included,updated_at
                ) VALUES(?,?,?,?)
                ON CONFLICT(canonical_group_id,merchant_normalized) DO UPDATE SET
                included=excluded.included,updated_at=excluded.updated_at""",
                (canonical_group_id, alias, int(alias in selected_aliases), now),
            )
        connection.commit()
        result = dict(connection.execute(
            "SELECT * FROM recurring_profiles WHERE canonical_group_id=?",
            (canonical_group_id,),
        ).fetchone())
        result["included_aliases"] = sorted(selected_aliases)
        return result
    finally:
        connection.close()


def mapping_payload(database: Path) -> dict:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        totals = connection.execute(
            """SELECT COUNT(*) merchants,
            SUM(has_uncategorized) needs_review,
            SUM(CASE WHEN has_uncategorized=0 THEN 1 ELSE 0 END) categorized
            FROM (SELECT merchant_normalized,MAX(user_category IS NULL AND provider_category IS NULL) has_uncategorized
                  FROM transactions GROUP BY merchant_normalized)"""
        ).fetchone()
        review = [dict(row) for row in connection.execute(
            """SELECT merchant_raw,merchant_normalized,COUNT(*) transactions,
            ROUND(SUM(ABS(CAST(charged_amount AS REAL))),2) amount
            FROM transactions WHERE user_category IS NULL AND provider_category IS NULL
            GROUP BY merchant_normalized ORDER BY transactions DESC,amount DESC LIMIT 1000"""
        )]
        imports = [dict(row) for row in connection.execute(
            """SELECT original_name,provider,card_last4,status,parsed_rows,inserted_rows,duplicate_rows,imported_at
            FROM imports ORDER BY id DESC LIMIT 8"""
        )]
        mappings = [dict(row) for row in connection.execute(
            "SELECT merchant_normalized,category,subcategory,updated_at FROM merchant_mappings ORDER BY updated_at DESC"
        )]
        categories = [row[0] for row in connection.execute(
            """SELECT DISTINCT category FROM (
                 SELECT user_category category FROM transactions WHERE user_category IS NOT NULL
                 UNION SELECT provider_category category FROM transactions WHERE provider_category IS NOT NULL
               ) WHERE category IS NOT NULL ORDER BY category"""
        )]
        return {"summary": dict(totals), "review_merchants": review, "recent_imports": imports,
                "mappings": mappings, "category_suggestions": categories}
    finally:
        connection.close()


def save_mapping(database: Path, merchant: str, category: str, subcategory: str) -> dict:
    merchant = merchant.strip()
    category = category.strip()
    subcategory = subcategory.strip()
    if not merchant or not category:
        raise ValueError("Merchant and category are required")
    connection = sqlite3.connect(database)
    try:
        now = datetime.now().astimezone().isoformat()
        connection.execute(
            """INSERT INTO merchant_mappings(merchant_normalized,category,subcategory,updated_at)
            VALUES(?,?,?,?) ON CONFLICT(merchant_normalized) DO UPDATE SET
            category=excluded.category,subcategory=excluded.subcategory,updated_at=excluded.updated_at""",
            (merchant, category, subcategory or None, now),
        )
        cursor = connection.execute(
            "UPDATE transactions SET user_category=?,user_subcategory=? WHERE merchant_normalized=?",
            (category, subcategory or None, merchant),
        )
        connection.commit()
        return {"status": "saved", "merchant_normalized": merchant, "category": category,
                "subcategory": subcategory or None, "transactions_updated": cursor.rowcount}
    finally:
        connection.close()


def merchants_payload(database: Path) -> dict:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        aliases = [dict(row) for row in connection.execute(
            """SELECT t.merchant_normalized,
            COALESCE(d.canonical_group_id,t.merchant_normalized) canonical_group_id,
            COALESCE(d.display_name,
              (SELECT recent.merchant_raw FROM transactions recent
               WHERE recent.merchant_normalized=t.merchant_normalized
               ORDER BY recent.transaction_date DESC,recent.id DESC LIMIT 1)) display_name,
            (SELECT recent.merchant_raw FROM transactions recent
             WHERE recent.merchant_normalized=t.merchant_normalized
             ORDER BY recent.transaction_date DESC,recent.id DESC LIMIT 1) merchant_raw,
            COALESCE(m.category,
              (SELECT COALESCE(sample.user_category,sample.provider_category,'Needs review')
               FROM transactions sample WHERE sample.merchant_normalized=t.merchant_normalized
               GROUP BY COALESCE(sample.user_category,sample.provider_category,'Needs review')
               ORDER BY COUNT(*) DESC LIMIT 1),'Needs review') category,
            m.subcategory,COUNT(*) transactions,
            ROUND(SUM(ABS(CAST(t.charged_amount AS REAL))),2) amount,
            MAX(t.transaction_date) last_seen
            FROM transactions t
            LEFT JOIN merchant_display_mappings d ON d.merchant_normalized=t.merchant_normalized
            LEFT JOIN merchant_mappings m ON m.merchant_normalized=t.merchant_normalized
            GROUP BY t.merchant_normalized,d.canonical_group_id,d.display_name,m.category,m.subcategory
            ORDER BY transactions DESC,t.merchant_normalized"""
        )]
        profiles = {
            row["canonical_group_id"]: dict(row) for row in connection.execute(
                """SELECT canonical_group_id,verdict,recurring_type,cadence,cadence_months,
                lifecycle_status,end_month,updated_at FROM recurring_profiles"""
            )
        }
        recurring_members = {
            (row["canonical_group_id"], row["merchant_normalized"]): bool(row["included"])
            for row in connection.execute(
                """SELECT canonical_group_id,merchant_normalized,included
                FROM recurring_profile_members"""
            )
        }
        grouped: dict[str, dict] = {}
        for alias in aliases:
            group_id = alias["canonical_group_id"]
            if group_id not in grouped:
                grouped[group_id] = {
                    "canonical_group_id": group_id,
                    "display_name": alias["display_name"],
                    "transactions": 0,
                    "amount": 0.0,
                    "last_seen": alias["last_seen"],
                    "categories": [],
                    "aliases": [],
                    "recurring_profile": profiles.get(group_id),
                }
            group = grouped[group_id]
            group["transactions"] += int(alias["transactions"])
            group["amount"] = round(group["amount"] + float(alias["amount"] or 0), 2)
            if alias["last_seen"] and (not group["last_seen"] or alias["last_seen"] > group["last_seen"]):
                group["last_seen"] = alias["last_seen"]
            if alias["category"] not in group["categories"]:
                group["categories"].append(alias["category"])
            group["aliases"].append({
                "merchant_normalized": alias["merchant_normalized"],
                "merchant_raw": alias["merchant_raw"],
                "category": alias["category"],
                "subcategory": alias["subcategory"],
                "transactions": int(alias["transactions"]),
                "recurring_included": recurring_members.get(
                    (group_id, alias["merchant_normalized"]), False
                ),
            })
        for group in grouped.values():
            if group["recurring_profile"]:
                group["recurring_profile"]["included_aliases"] = [
                    alias["merchant_normalized"] for alias in group["aliases"]
                    if alias["recurring_included"]
                ]
        merchants = sorted(grouped.values(), key=lambda item: (-item["transactions"], item["display_name"]))
        categories = [row[0] for row in connection.execute(
            """SELECT DISTINCT category FROM (
                 SELECT category FROM merchant_mappings
                 UNION SELECT user_category category FROM transactions WHERE user_category IS NOT NULL
                 UNION SELECT provider_category category FROM transactions WHERE provider_category IS NOT NULL
               ) WHERE category IS NOT NULL ORDER BY category"""
        )]
        return {
            "summary": {
                "display_identities": len(merchants),
                "mapped_aliases": len(aliases),
                "transactions": sum(item["transactions"] for item in merchants),
                "multiple_categories": sum(len(item["categories"]) > 1 for item in merchants),
                "recurring": sum(
                    item["recurring_profile"] is not None
                    and item["recurring_profile"]["verdict"] == "recurring"
                    for item in merchants
                ),
            },
            "categories": categories,
            "merchants": merchants,
        }
    finally:
        connection.close()


def save_merchant(database: Path, group_id: str, display_name: str, aliases: list[dict]) -> dict:
    group_id = group_id.strip()
    display_name = display_name.strip()
    if not group_id or not display_name:
        raise ValueError("Merchant group and display name are required")
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        existing = [row[0] for row in connection.execute(
            """SELECT DISTINCT t.merchant_normalized FROM transactions t
            LEFT JOIN merchant_display_mappings d ON d.merchant_normalized=t.merchant_normalized
            WHERE COALESCE(d.canonical_group_id,t.merchant_normalized)=?""",
            (group_id,),
        )]
        if not existing:
            raise ValueError("Merchant group was not found")
        allowed = set(existing)
        requested = {str(item.get("merchant_normalized", "")).strip(): item for item in aliases}
        if any(merchant not in allowed for merchant in requested):
            raise ValueError("A merchant alias does not belong to this group")
        now = datetime.now().astimezone().isoformat()
        for merchant in existing:
            connection.execute(
                """INSERT INTO merchant_display_mappings(
                merchant_normalized,canonical_group_id,display_name,updated_at
                ) VALUES(?,?,?,?) ON CONFLICT(merchant_normalized) DO UPDATE SET
                canonical_group_id=excluded.canonical_group_id,
                display_name=excluded.display_name,updated_at=excluded.updated_at""",
                (merchant, group_id, display_name, now),
            )
        transactions_updated = 0
        category_rules_updated = 0
        for merchant, item in requested.items():
            category = str(item.get("category", "")).strip()
            subcategory = str(item.get("subcategory", "")).strip()
            if not category:
                raise ValueError("Every edited alias needs a category")
            connection.execute(
                """INSERT INTO merchant_mappings(merchant_normalized,category,subcategory,updated_at)
                VALUES(?,?,?,?) ON CONFLICT(merchant_normalized) DO UPDATE SET
                category=excluded.category,subcategory=excluded.subcategory,updated_at=excluded.updated_at""",
                (merchant, category, subcategory or None, now),
            )
            cursor = connection.execute(
                "UPDATE transactions SET user_category=?,user_subcategory=? WHERE merchant_normalized=?",
                (category, subcategory or None, merchant),
            )
            transactions_updated += cursor.rowcount
            category_rules_updated += 1
        connection.commit()
        return {
            "status": "saved",
            "display_name": display_name,
            "aliases_updated": len(existing),
            "category_rules_updated": category_rules_updated,
            "transactions_updated": transactions_updated,
        }
    finally:
        connection.close()


def save_transaction_category(database: Path, transaction_id: int, category: str, subcategory: str) -> dict:
    category = category.strip()
    subcategory = subcategory.strip()
    if transaction_id <= 0 or not category:
        raise ValueError("Transaction and category are required")
    connection = sqlite3.connect(database)
    try:
        row = connection.execute("SELECT merchant_raw FROM transactions WHERE id=?", (transaction_id,)).fetchone()
        if not row:
            raise ValueError("Transaction was not found")
        now = datetime.now().astimezone().isoformat()
        connection.execute(
            """INSERT INTO transaction_category_overrides(transaction_id,category,subcategory,updated_at)
            VALUES(?,?,?,?) ON CONFLICT(transaction_id) DO UPDATE SET
            category=excluded.category,subcategory=excluded.subcategory,updated_at=excluded.updated_at""",
            (transaction_id, category, subcategory or None, now),
        )
        connection.commit()
        return {
            "status": "saved",
            "transaction_id": transaction_id,
            "merchant_raw": row[0],
            "category": category,
            "subcategory": subcategory or None,
        }
    finally:
        connection.close()


def save_transaction_adjustment(
    database: Path,
    transaction_id: int,
    reimbursed_amount: float,
    reimbursement_date: str,
    note: str,
    remove: bool = False,
) -> dict:
    if transaction_id <= 0:
        raise ValueError("Transaction is required")
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT merchant_raw,CAST(charged_amount AS REAL) amount FROM transactions WHERE id=?",
            (transaction_id,),
        ).fetchone()
        if not row:
            raise ValueError("Transaction was not found")
        charge = float(row["amount"] or 0)
        if charge <= 0:
            raise ValueError("Only positive card charges can be marked as reimbursed")
        if remove:
            connection.execute(
                "DELETE FROM transaction_spending_adjustments WHERE transaction_id=?",
                (transaction_id,),
            )
            connection.commit()
            return {
                "status": "removed", "transaction_id": transaction_id,
                "merchant_raw": row["merchant_raw"], "personal_amount": round(charge, 2),
            }
        if not math.isfinite(reimbursed_amount) or reimbursed_amount <= 0:
            raise ValueError("Reimbursed amount must be greater than zero")
        if reimbursed_amount > charge + 0.005:
            raise ValueError("Reimbursed amount cannot exceed the original card charge")
        reimbursed_amount = round(min(reimbursed_amount, charge), 2)
        reimbursement_date = reimbursement_date.strip()
        if reimbursement_date:
            try:
                date.fromisoformat(reimbursement_date)
            except ValueError as error:
                raise ValueError("Reimbursement date must be a valid date") from error
        note = note.strip()
        if len(note) > 500:
            raise ValueError("Note must be 500 characters or fewer")
        adjustment_type = (
            "full_reimbursement" if abs(reimbursed_amount - charge) < 0.005
            else "partial_reimbursement"
        )
        now = datetime.now().astimezone().isoformat()
        connection.execute(
            """INSERT INTO transaction_spending_adjustments(
            transaction_id,adjustment_type,reimbursed_amount,reimbursement_date,note,updated_at
            ) VALUES(?,?,?,?,?,?) ON CONFLICT(transaction_id) DO UPDATE SET
            adjustment_type=excluded.adjustment_type,
            reimbursed_amount=excluded.reimbursed_amount,
            reimbursement_date=excluded.reimbursement_date,
            note=excluded.note,updated_at=excluded.updated_at""",
            (
                transaction_id, adjustment_type, f"{reimbursed_amount:.2f}",
                reimbursement_date or None, note or None, now,
            ),
        )
        connection.commit()
        return {
            "status": "saved", "transaction_id": transaction_id,
            "merchant_raw": row["merchant_raw"], "adjustment_type": adjustment_type,
            "reimbursed_amount": reimbursed_amount,
            "personal_amount": round(charge - reimbursed_amount, 2),
        }
    finally:
        connection.close()


OBSERVATION_RESOLUTIONS = {
    "POSSIBLE DUPLICATE": "not_duplicate",
    "ADDITIONAL RECURRING CHARGE": "expected_charge",
    "UNUSUAL TRANSACTION": "not_unusual",
}


def observation_reviews_payload(database: Path) -> dict:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """SELECT finding_key,observation_type,resolution,month,transaction_ids,
            recurring_series_id,occurrence_start,occurrence_end,merchant_label,reviewed_at,updated_at
            FROM observation_reviews WHERE active=1 ORDER BY updated_at DESC"""
        ).fetchall()
        reviews = []
        for row in rows:
            item = dict(row)
            try:
                item["transaction_ids"] = json.loads(item["transaction_ids"] or "[]")
            except json.JSONDecodeError:
                item["transaction_ids"] = []
            reviews.append(item)
        return {"reviews": reviews}
    finally:
        connection.close()


def save_observation_review(
    database: Path,
    finding_key: str,
    observation_type: str,
    resolution: str,
    month: str,
    transaction_ids: object,
    recurring_series_id: str = "",
    occurrence_start: str = "",
    occurrence_end: str = "",
    merchant_label: str = "",
    remove: bool = False,
) -> dict:
    finding_key = finding_key.strip()
    observation_type = observation_type.strip().upper()
    resolution = resolution.strip()
    month = month.strip()
    recurring_series_id = recurring_series_id.strip()
    occurrence_start = occurrence_start.strip()
    occurrence_end = occurrence_end.strip()
    merchant_label = merchant_label.strip()
    expected_resolution = OBSERVATION_RESOLUTIONS.get(observation_type)
    if not expected_resolution:
        raise ValueError("This observation type cannot be resolved")
    if not finding_key or len(finding_key) > 1000 or not finding_key.startswith(f"{observation_type}:"):
        raise ValueError("A valid finding key is required")
    if resolution != expected_resolution:
        raise ValueError("Invalid resolution for this observation type")
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError("A valid observation month is required")
    if not isinstance(transaction_ids, list):
        raise ValueError("Transaction IDs must be a list")
    try:
        ids = sorted({int(value) for value in transaction_ids if int(value) > 0})
    except (TypeError, ValueError) as error:
        raise ValueError("Transaction IDs must be positive integers") from error
    if observation_type == "POSSIBLE DUPLICATE" and len(ids) < 2:
        raise ValueError("A duplicate review requires at least two transactions")
    if observation_type == "UNUSUAL TRANSACTION" and len(ids) != 1:
        raise ValueError("An unusual-transaction review requires one transaction")
    if observation_type == "ADDITIONAL RECURRING CHARGE" and (len(ids) < 2 or not recurring_series_id):
        raise ValueError("A recurring-charge review requires its series and transactions")
    for value in (occurrence_start, occurrence_end):
        if value:
            try:
                date.fromisoformat(value)
            except ValueError as error:
                raise ValueError("Occurrence dates must be valid dates") from error
    connection = sqlite3.connect(database)
    try:
        if ids:
            placeholders = ",".join("?" for _ in ids)
            found = connection.execute(
                f"SELECT COUNT(*) FROM transactions WHERE id IN ({placeholders})", ids
            ).fetchone()[0]
            if found != len(ids):
                raise ValueError("One or more reviewed transactions were not found")
        now = datetime.now().astimezone().isoformat()
        if remove:
            changed = connection.execute(
                """UPDATE observation_reviews SET active=0,updated_at=?
                WHERE finding_key=? AND active=1""",
                (now, finding_key),
            ).rowcount
            connection.commit()
            return {"status": "restored", "finding_key": finding_key, "changed": bool(changed)}
        connection.execute(
            """INSERT INTO observation_reviews(
            finding_key,observation_type,resolution,month,transaction_ids,recurring_series_id,
            occurrence_start,occurrence_end,merchant_label,active,reviewed_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,1,?,?)
            ON CONFLICT(finding_key) DO UPDATE SET
            observation_type=excluded.observation_type,resolution=excluded.resolution,
            month=excluded.month,transaction_ids=excluded.transaction_ids,
            recurring_series_id=excluded.recurring_series_id,
            occurrence_start=excluded.occurrence_start,occurrence_end=excluded.occurrence_end,
            merchant_label=excluded.merchant_label,active=1,updated_at=excluded.updated_at""",
            (
                finding_key, observation_type, resolution, month,
                json.dumps(ids, separators=(",", ":")), recurring_series_id or None,
                occurrence_start or None, occurrence_end or None, merchant_label or None, now, now,
            ),
        )
        connection.commit()
        return {"status": "reviewed", "finding_key": finding_key, "resolution": resolution}
    finally:
        connection.close()


class ClearSpendHandler(BaseHTTPRequestHandler):
    server_version = "ClearSpend/0.1"

    @property
    def app(self) -> "ClearSpendServer":
        return self.server  # type: ignore[return-value]

    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json({"status": "ok", "mode": "local", "database": self.app.database.exists()})
            return
        if parsed.path == "/api/dashboard":
            query = parse_qs(parsed.query)
            period = query.get("period", ["month"])[0]
            card = query.get("card", ["all"])[0]
            month = query.get("month", [""])[0]
            if period not in {"month", "year", "all"}:
                self.send_json({"error": "Invalid period"}, 400)
                return
            try:
                self.send_json(dashboard_payload(self.app.database, period, card, month))
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed.path in {"/api/transactions", "/api/categories"}:
            query = parse_qs(parsed.query)
            period = query.get("period", ["month"])[0]
            card = query.get("card", ["all"])[0]
            month = query.get("month", [""])[0]
            if period not in {"month", "year", "all"}:
                self.send_json({"error": "Invalid period"}, 400)
                return
            try:
                if parsed.path == "/api/transactions":
                    self.send_json(transactions_payload(
                        self.app.database,
                        period,
                        card,
                        query.get("q", [""])[0],
                        month,
                        query.get("category", [""])[0],
                    ))
                else:
                    self.send_json(categories_payload(self.app.database, period, card, month))
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed.path == "/api/mapping":
            try:
                self.send_json(mapping_payload(self.app.database))
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed.path == "/api/merchants":
            try:
                self.send_json(merchants_payload(self.app.database))
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed.path == "/api/recurring":
            query = parse_qs(parsed.query)
            period = query.get("period", ["month"])[0]
            if period not in {"month", "year", "all"}:
                self.send_json({"error": "Invalid period"}, 400)
                return
            try:
                self.send_json(recurring_payload(
                    self.app.database,
                    period,
                    query.get("card", ["all"])[0],
                    query.get("month", [""])[0],
                ))
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed.path == "/api/observation-reviews":
            try:
                self.send_json(observation_reviews_payload(self.app.database))
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed_path = urlparse(self.path).path
        if parsed_path == "/api/mapping":
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 1024 * 1024)
                payload = json.loads(self.rfile.read(length) or b"{}")
                self.send_json(save_mapping(
                    self.app.database,
                    str(payload.get("merchant_normalized", "")),
                    str(payload.get("category", "")),
                    str(payload.get("subcategory", "")),
                ))
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed_path == "/api/merchants":
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 1024 * 1024)
                payload = json.loads(self.rfile.read(length) or b"{}")
                aliases = payload.get("aliases", [])
                if not isinstance(aliases, list):
                    raise ValueError("Aliases must be a list")
                self.send_json(save_merchant(
                    self.app.database,
                    str(payload.get("canonical_group_id", "")),
                    str(payload.get("display_name", "")),
                    aliases,
                ))
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed_path == "/api/transaction-category":
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 1024 * 1024)
                payload = json.loads(self.rfile.read(length) or b"{}")
                self.send_json(save_transaction_category(
                    self.app.database,
                    int(payload.get("transaction_id", 0)),
                    str(payload.get("category", "")),
                    str(payload.get("subcategory", "")),
                ))
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed_path == "/api/transaction-adjustment":
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 1024 * 1024)
                payload = json.loads(self.rfile.read(length) or b"{}")
                self.send_json(save_transaction_adjustment(
                    self.app.database,
                    int(payload.get("transaction_id", 0)),
                    float(payload.get("reimbursed_amount", 0) or 0),
                    str(payload.get("reimbursement_date", "")),
                    str(payload.get("note", "")),
                    bool(payload.get("remove", False)),
                ))
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed_path == "/api/observation-review":
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 1024 * 1024)
                payload = json.loads(self.rfile.read(length) or b"{}")
                self.send_json(save_observation_review(
                    self.app.database,
                    str(payload.get("finding_key", "")),
                    str(payload.get("observation_type", "")),
                    str(payload.get("resolution", "")),
                    str(payload.get("month", "")),
                    payload.get("transaction_ids", []),
                    str(payload.get("recurring_series_id", "")),
                    str(payload.get("occurrence_start", "")),
                    str(payload.get("occurrence_end", "")),
                    str(payload.get("merchant_label", "")),
                    bool(payload.get("remove", False)),
                ))
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed_path == "/api/recurring-profile":
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 1024 * 1024)
                payload = json.loads(self.rfile.read(length) or b"{}")
                self.send_json(save_recurring_profile(
                    self.app.database,
                    str(payload.get("canonical_group_id", "")),
                    str(payload.get("recurring_type", "")),
                    str(payload.get("cadence", "")),
                    str(payload.get("lifecycle_status", "")),
                    str(payload.get("end_month", "")),
                ))
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed_path == "/api/recurring-profile/manage":
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 1024 * 1024)
                payload = json.loads(self.rfile.read(length) or b"{}")
                self.send_json(manage_recurring_profile(
                    self.app.database,
                    str(payload.get("canonical_group_id", "")),
                    str(payload.get("verdict", "")),
                    str(payload.get("recurring_type", "")),
                    str(payload.get("cadence", "")),
                    str(payload.get("lifecycle_status", "active")),
                    str(payload.get("end_month", "")),
                    payload.get("included_aliases") if isinstance(payload.get("included_aliases"), list) else None,
                ))
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed_path == "/api/import/commit":
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 8 * 1024 * 1024)
                payload = json.loads(self.rfile.read(length) or b"{}")
                batch_id = str(payload.get("batch_id", ""))
                batch = self.app.staged_imports.get(batch_id)
                if not batch:
                    raise ValueError("Staged import was not found or the server was restarted")
                decisions = payload.get("decisions", [])
                if not isinstance(decisions, list):
                    raise ValueError("Decisions must be a list")
                reconciled_files = payload.get("reconciled_files", [])
                if not isinstance(reconciled_files, list):
                    raise ValueError("Reconciled files must be a list")
                analysis = analyze_staged_files(
                    self.app.database,
                    [(item["filename"], item["path"]) for item in batch["uploads"]],
                )
                required_reconciliation = {
                    item["filename"] for item in analysis["files"]
                    if item["kind"] == "statement" and item["status"] == "ready"
                    and item["reconciliation"]["status"] == "manual_required"
                }
                missing_reconciliation = required_reconciliation - {str(item) for item in reconciled_files}
                if missing_reconciliation:
                    missing = ", ".join(sorted(missing_reconciliation))
                    raise ValueError(f"Confirm the statement total before importing: {missing}")
                result = commit_staged_batch(self.app.database, batch, decisions)
                for item in batch["uploads"]:
                    item["path"].unlink(missing_ok=True)
                self.app.staged_imports.pop(batch_id, None)
                self.send_json(result)
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed_path not in {"/api/import", "/api/import/analyze"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            self.send_json({"error": "Expected multipart file upload"}, 400)
            return
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type},
        )
        items = form["files"] if "files" in form else []
        if not isinstance(items, list):
            items = [items]
        results = []
        is_staged = parsed_path == "/api/import/analyze"
        batch_id = uuid.uuid4().hex
        upload_dir = self.app.database.parent / ("staging" if is_staged else "uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        staged_uploads: list[dict] = []
        for item in items:
            filename = Path(getattr(item, "filename", "") or "statement").name
            extension = Path(filename).suffix.lower()
            if extension not in {".xlsx", ".pdf"}:
                results.append({"filename": filename, "status": "unsupported", "error": "Use XLSX or PDF"})
                continue
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
            with tempfile.NamedTemporaryFile(dir=upload_dir, suffix=f"-{safe_name}", delete=False) as output:
                while True:
                    chunk = item.file.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                upload_path = Path(output.name)
            if is_staged:
                staged_uploads.append({"filename": filename, "path": upload_path})
                continue
            database = ImportDatabase(self.app.database)
            try:
                try:
                    result = database.import_file(upload_path)
                    if result.get("import_id"):
                        table = "income_imports" if result.get("kind") == "income" else "imports"
                        database.connection.execute(
                            f"UPDATE {table} SET original_name = ? WHERE id = ?", (filename, result["import_id"])
                        )
                        database.connection.commit()
                except Exception as error:
                    upload_path.unlink(missing_ok=True)
                    result = {"status": "error", "error": str(error)}
            finally:
                database.close()
            result["filename"] = filename
            if result["status"] in {"duplicate_file", "duplicate_content"}:
                upload_path.unlink(missing_ok=True)
            results.append(result)
        if is_staged:
            try:
                analysis = analyze_staged_files(
                    self.app.database,
                    [(item["filename"], item["path"]) for item in staged_uploads],
                )
            except Exception as error:
                for item in staged_uploads:
                    item["path"].unlink(missing_ok=True)
                self.send_json({"error": str(error), "results": results}, 400)
                return
            self.app.staged_imports[batch_id] = {"uploads": staged_uploads, "created_at": datetime.now().isoformat()}
            analysis["batch_id"] = batch_id
            analysis["upload_errors"] = results
            self.send_json(analysis)
        else:
            self.send_json({"results": results})

    def serve_static(self, requested_path: str) -> None:
        relative = requested_path.lstrip("/") or "index.html"
        candidate = (self.app.static_dir / relative).resolve()
        if self.app.static_dir.resolve() not in candidate.parents and candidate != self.app.static_dir.resolve():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if candidate.is_dir():
            candidate /= "index.html"
        if not candidate.is_file():
            candidate = self.app.static_dir / "index.html"
        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


class ClearSpendServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], static_dir: Path, database: Path):
        super().__init__(address, ClearSpendHandler)
        self.static_dir = static_dir
        self.database = database
        self.staged_imports: dict[str, dict] = {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local ClearSpend dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--static-dir", type=Path)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[2]
    database = (args.database or project_root / "data" / "clearspend.db").resolve()
    static_dir = (args.static_dir or project_root / "dist").resolve()
    migration = ImportDatabase(database)
    migration.close()
    server = ClearSpendServer((args.host, args.port), static_dir, database)
    print(f"ClearSpend is running at http://{args.host}:{args.port}")
    print(f"Database: {database}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ClearSpend")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
