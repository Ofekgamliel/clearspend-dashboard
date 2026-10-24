from __future__ import annotations

import argparse
import cgi
import hashlib
import json
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
            COALESCE(SUM(CASE WHEN CAST(charged_amount AS REAL) > 0 THEN CAST(charged_amount AS REAL) ELSE 0 END),0) spent,
            COALESCE(ABS(SUM(CASE WHEN CAST(charged_amount AS REAL) < 0 THEN CAST(charged_amount AS REAL) ELSE 0 END)),0) refunds,
            COUNT(*) transactions,
            COUNT(DISTINCT {REPORTING_DATE_SQL}) active_days
            FROM transactions WHERE {where}""",
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
            COALESCE(SUM(CASE WHEN CAST(charged_amount AS REAL)>0 THEN CAST(charged_amount AS REAL) ELSE 0 END),0) spent,
            COALESCE(ABS(SUM(CASE WHEN CAST(charged_amount AS REAL)<0 THEN CAST(charged_amount AS REAL) ELSE 0 END)),0) refunds
            FROM transactions WHERE {REPORTING_MONTH_SQL} BETWEEN ? AND ?""",
            period_parameters,
        ).fetchone()
        income_total = float(income_row["total"])
        all_card_spent = float(all_card_spending["spent"])
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
            SUM(CASE WHEN CAST(charged_amount AS REAL)>0 THEN CAST(charged_amount AS REAL) ELSE 0 END)
            - ABS(SUM(CASE WHEN CAST(charged_amount AS REAL)<0 THEN CAST(charged_amount AS REAL) ELSE 0 END)) net
            FROM transactions WHERE {REPORTING_MONTH_SQL} BETWEEN ? AND ? GROUP BY {REPORTING_MONTH_SQL}""",
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
            ROUND(SUM(CASE WHEN CAST(t.charged_amount AS REAL)>0 THEN CAST(t.charged_amount AS REAL) ELSE 0 END),2) amount,
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
            ROUND(SUM(CASE WHEN CAST(t.charged_amount AS REAL)>0 THEN CAST(t.charged_amount AS REAL) ELSE 0 END),2) amount,
            COUNT(*) transactions FROM transactions t
            LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id WHERE {where}
            GROUP BY COALESCE(o.category,t.user_category,t.provider_category,'Needs review') HAVING amount > 0 ORDER BY amount DESC""",
            parameters,
        )]
        for item in categories:
            item["share"] = round((item["amount"] / spent * 100), 1) if spent else 0

        recent = [dict(row) for row in connection.execute(
            f"""SELECT t.merchant_raw,COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
            COALESCE(o.subcategory,t.user_subcategory) subcategory,t.provider,t.card_last4,
            t.transaction_date,t.billing_date,t.billing_month,t.billing_month_source,
            CAST(t.charged_amount AS REAL) amount,t.charged_currency
            FROM transactions t LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
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
                       CAST(t.charged_amount AS REAL) amount,1 purchases,0 installment_plans
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
                ROUND(SUM(CAST(charged_amount AS REAL)),2) amount
                FROM transactions WHERE {where} GROUP BY {REPORTING_MONTH_SQL} ORDER BY bucket""",
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
            f"""SELECT merchant_raw,CAST(charged_amount AS REAL) amount FROM transactions
            WHERE {where} AND CAST(charged_amount AS REAL)>0 ORDER BY amount DESC LIMIT 1""",
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
                "charges": round(all_card_spent, 2),
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
            CAST(original_amount AS REAL) original_amount,original_currency,
            transaction_type,voucher_number,notes,execution_method,exchange_rate
            FROM transactions t LEFT JOIN merchant_display_mappings d
              ON d.merchant_normalized=t.merchant_normalized
            LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
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
            f"SELECT COALESCE(SUM(CASE WHEN CAST(charged_amount AS REAL)>0 THEN CAST(charged_amount AS REAL) ELSE 0 END),0) FROM transactions WHERE {where}",
            parameters,
        ).fetchone()[0])
        rows = [dict(row) for row in connection.execute(
            f"""SELECT COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
            ROUND(SUM(CASE WHEN CAST(t.charged_amount AS REAL)>0 THEN CAST(t.charged_amount AS REAL) ELSE 0 END),2) amount,
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
            })
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
